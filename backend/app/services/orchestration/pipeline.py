"""End-to-end research pipeline orchestration."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.history_repository import HistoryRepository
from app.db.repositories.persistence_repository import PersistenceRepository
from app.services.analogs import AnalogService
from app.services.cache.redis_cache import RedisCache
from app.services.collectors.news_collector import NewsCollectorService
from app.services.compression.narrative import NarrativeCompressionService
from app.services.deliberation.llm_clients.registry import ALL_DIL_MODEL_KEYS
from app.services.deliberation.roles import get_active_desks
from app.services.embeddings.cleaner import NewsCleanerService
from app.services.event_extraction.rules import EventExtractionService
from app.services.impact_scoring.scorer import EventImpactScoringService
from app.services.llm.claude_report import ClaudeReportService
from app.services.market.options_chain import OptionsChainService
from app.services.market.polygon import MarketDataService
from app.services.options import OptionsIntelligenceService
from app.services.qdrant.store import QdrantStoreService
from app.services.relevance import classify_article
from app.services.sentiment.finbert import SentimentService
from app.services.summary import extract_executive_summary

log = structlog.get_logger(__name__)

ProgressCb = Callable[[str, str], Awaitable[None]]


class ResearchPipelineService:
    """Coordinates collectors → embeddings → FinBERT → events → market → impact → LLM."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        qdrant: QdrantStoreService | None,
        cache: RedisCache | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._qdrant = qdrant
        self._cache = cache
        self._persist = PersistenceRepository(session)
        self._history = HistoryRepository(session)
        self._analogs = AnalogService(session, settings, qdrant)

    async def run(
        self,
        ticker: str,
        days: int = 7,
        *,
        persist: bool = True,
        on_progress: ProgressCb | None = None,
        schedule_dil: bool = True,
    ) -> dict[str, Any]:
        run_id = str(uuid4())
        start_t = time.monotonic()
        t = ticker.upper()
        log.info("pipeline.start", run_id=run_id, ticker=t, days=days)

        async def prog(stage: str, message: str) -> None:
            if on_progress:
                await on_progress(stage, message)

        await prog("collect", "Fetching news from external APIs")
        collector = NewsCollectorService(self._settings, t, days)
        raw = await collector.collect()
        if persist:
            await self._persist.persist_raw_articles(raw)

        await prog("clean", "Embedding + deduplication")
        cleaner = NewsCleanerService(self._settings, self._qdrant)
        cleaned = cleaner.clean(raw)

        await prog("sentiment", "FinBERT scoring")
        sentiment = SentimentService(self._settings)
        with_sent = sentiment.analyze(cleaned)

        await prog("events", "Rule-based event extraction")
        events = EventExtractionService()
        with_events = events.extract(with_sent)

        await prog("market", "OHLCV + returns")
        market = MarketDataService(self._settings, t)
        bars: list[Any] = []
        try:
            bars = await market.fetch_ohlcv(days + 5)
            returns = market.compute_daily_returns(bars)
            vol_map = market.compute_intraday_volatility(bars)
            with_events = market.join_price_to_articles(with_events, returns, vol_map)
            vol_regime = market.get_volatility_regime(bars)
            last_close = market.get_current_price(bars)
            if persist:
                await self._persist.persist_ohlcv(bars)
            price_ctx = {
                "last_close": last_close,
                "volatility_regime": vol_regime,
                "recent_returns": dict(list(returns.items())[-7:]),
                "avg_daily_vol_pct": round(
                    sum(abs(v) for v in returns.values()) / max(len(returns), 1), 2
                ),
            }
        except Exception as e:
            log.warning("market_data.failed", error=str(e))
            vol_regime = "medium"
            price_ctx = {"last_close": None, "volatility_regime": vol_regime, "error": str(e)}

        await prog("impact", "Impact scoring")
        scorer = EventImpactScoringService()
        with_impact = scorer.score(with_events, volatility_regime=vol_regime)
        if persist:
            await self._persist.persist_processed_articles(with_impact)

        await prog("compress", "Narrative compression")
        compressor = NarrativeCompressionService(self._settings)
        if self._settings.relevance_filter_enabled:
            allow_macro = self._settings.relevance_include_macro_in_narrative
            allowed_tiers = (
                {"direct", "related_sector", "macro"}
                if allow_macro
                else {"direct", "related_sector"}
            )
            narrative_input = [
                a
                for a in with_impact
                if classify_article(a.headline, a.content, t).tier in allowed_tiers
            ]
            # Fallback to full set if the filter removed everything (rare; preserves continuity).
            if not narrative_input:
                narrative_input = with_impact
        else:
            narrative_input = with_impact
        clusters = compressor.compress(narrative_input)

        await prog("vectors", "Qdrant upsert")
        if self._qdrant:
            self._qdrant.upsert_articles(with_impact)

        await prog("report", "Claude synthesis")
        reporter = ClaudeReportService(self._settings)
        report = await reporter.generate(t, clusters, price_ctx)

        unique = [a for a in with_impact if not a.is_duplicate]
        dupes = [a for a in with_impact if a.is_duplicate]
        top_movers = sorted(unique, key=lambda a: a.impact_score, reverse=True)[:5]

        price_snapshot: dict[str, Any] = {}
        if len(bars) >= 2:
            last_bar, prev_bar = bars[-1], bars[-2]
            window = bars[-min(20, len(bars)) :]
            avg_vol = sum(b.volume for b in window) / len(window)
            pct_change = None
            if prev_bar.close:
                pct_change = round((last_bar.close - prev_bar.close) / prev_bar.close * 100, 2)
            vol_ratio = round(last_bar.volume / avg_vol, 2) if avg_vol > 0 else None
            price_snapshot = {
                "last_close": last_bar.close,
                "prior_close": prev_bar.close,
                "last_session_change_pct": pct_change,
                "last_volume": last_bar.volume,
                "avg_volume_20d": int(round(avg_vol)),
                "volume_vs_avg": vol_ratio,
            }

        ohlcv_series = [
            {"c": b.close, "h": b.high, "l": b.low, "v": b.volume}
            for b in bars[-60:]
        ]

        relevance_enabled = self._settings.relevance_filter_enabled
        ordered = sorted(unique, key=lambda x: x.published_at, reverse=True)
        article_evidence: list[dict[str, Any]] = []
        relevance_counts = {"direct": 0, "related_sector": 0, "macro": 0, "unrelated": 0}
        for a in ordered:
            result = classify_article(a.headline, a.content, t) if relevance_enabled else None
            tier = result.tier if result else "direct"
            relevance_counts[tier] = relevance_counts.get(tier, 0) + 1
            if relevance_enabled and tier == "unrelated":
                continue
            row: dict[str, Any] = {
                "headline": a.headline,
                "source": a.source,
                "url": a.url or "",
                "published_at": a.published_at.isoformat(),
                "sentiment_score": round(a.sentiment_score, 4),
                "sentiment_label": a.sentiment_label,
                "impact_score": round(a.impact_score, 4),
                "reliability_score": a.reliability_score,
                "event_type": a.event_type,
                "abnormal_return": a.abnormal_return,
            }
            if result is not None:
                row["relevance_tier"] = result.tier
                row["relevance_score"] = round(result.score, 3)
                row["relevance_reasons"] = result.reasons[:2]
            article_evidence.append(row)
            if len(article_evidence) >= 60:
                break

        report["_pipeline_meta"] = {
            "run_id": run_id,
            "raw_articles": len(raw),
            "after_dedupe": len(unique),
            "duplicates_removed": len(dupes),
            "clusters_to_claude": len(clusters),
            "sources": sorted({a.source for a in unique}),
            "volatility_regime": vol_regime,
            "price_snapshot": price_snapshot,
            "ohlcv_series": ohlcv_series,
            "article_evidence": article_evidence,
            "relevance_stats": relevance_counts if relevance_enabled else None,
            "top_impact_events": [
                {
                    "headline": a.headline,
                    "source": a.source,
                    "url": a.url or "",
                    "impact": a.impact_score,
                    "event": a.event_type,
                    "abnormal_return": a.abnormal_return,
                }
                for a in top_movers
            ],
            "data_mode": "real",
            "elapsed_s": round(time.monotonic() - start_t, 2),
            "run_at": datetime.now(UTC).isoformat(),
        }

        if self._settings.options_enabled:
            try:
                live_iv_pct: float | None = None
                if self._settings.options_use_live_iv:
                    try:
                        chain = OptionsChainService(self._settings)
                        live_iv_pct = await chain.fetch_atm_iv_pct(
                            t, target_dte=self._settings.options_default_horizon_days
                        )
                    except Exception as iv_exc:  # pragma: no cover - defensive
                        log.warning("options_intelligence.live_iv_failed", error=str(iv_exc))
                        live_iv_pct = None
                options_service = OptionsIntelligenceService(self._settings)
                options_block = options_service.compute(
                    last_close=price_snapshot.get("last_close") if price_snapshot else None,
                    bars=bars,
                    volatility_regime=vol_regime,
                    key_events=report.get("key_events") or [],
                    articles_analyzed=report.get("articles_analyzed"),
                    data_mode=report.get("data_mode")
                    or report["_pipeline_meta"].get("data_mode"),
                    live_iv_pct=live_iv_pct,
                )
                if options_block is not None:
                    report["options_intelligence"] = options_block.model_dump()
            except Exception as exc:  # pragma: no cover - never break the pipeline
                log.warning("options_intelligence.failed", error=str(exc))

        # Phase 7 — Historical Analog Engine. Wire the AnalogService into
        # _pipeline_meta and project the *current* Reverse-BWB geometry
        # onto each analog's forward price path to compute win-rate /
        # credit-retained / max-loss-frequency aggregates.
        try:
            options_intel = report.get("options_intelligence") or {}
            geometry = options_intel.get("structure_geometry") or {}
            if options_intel and geometry:
                # Pick the most common impactful event type for the SQL
                # exact-event matcher; fall back to "Macro".
                event_type = "Macro"
                for ev in (report.get("key_events") or []):
                    if ev.get("event_type"):
                        event_type = str(ev["event_type"])
                        break
                analog_rows = await self._analogs.fetch_analogs(
                    t, event_type, limit=15
                )
                if analog_rows:
                    from app.services.analogs.setup_simulator import (
                        simulate_analog_setups,
                    )

                    simulated = await simulate_analog_setups(
                        session=self._session,
                        ticker=t,
                        analogs=analog_rows,
                        current_spot=float(geometry.get("spot") or 0.0),
                        current_body=float(geometry.get("body_strike") or 0.0),
                        wing_width_pct=float(geometry.get("wing_width_pct") or 0.0),
                        credit=float(geometry.get("credit") or 0.0),
                        dte=int(geometry.get("dte") or 0),
                    )
                    report["_pipeline_meta"]["historical_analogs"] = simulated[
                        "matches"
                    ]
                    report["_pipeline_meta"]["historical_analog_aggregates"] = (
                        simulated["aggregates"]
                    )
        except Exception as exc:  # pragma: no cover - never break the pipeline
            log.warning("analogs.simulation_failed", error=str(exc))

        # Stage-1 executive-summary extraction (options-only). The DIL runner
        # re-extracts once consensus completes so the grid card upgrades from
        # neutral outlook/confidence to DIL-backed values without an extra
        # round-trip from the client. Failures must never break the pipeline.
        try:
            report["executive_summary"] = extract_executive_summary(report).model_dump()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("executive_summary.extract_failed", error=str(exc))

        report["deliberation_layer"] = {
            "status": "pending",
            "run_id": run_id,
            "started_at": datetime.now(UTC).isoformat(),
            "models_requested": list(ALL_DIL_MODEL_KEYS),
            "desks_requested": [d.key for d in get_active_desks(self._settings)],
        }

        report_id_str: str | None = None
        if persist:
            report_id = await self._persist.persist_report(t, f"{days}d", report)
            report_id_str = str(report_id)
            report["_pipeline_meta"]["report_id"] = report_id_str

            # The watchlist batch path runs the orchestrator synchronously
            # right after this method returns, so callers opt out of the
            # async kick-off via ``schedule_dil=False`` to avoid a duplicate
            # run.
            if (
                schedule_dil
                and self._settings.dil_enabled
                and report_id_str
            ):
                from app.services.deliberation.runner import schedule_deliberation

                schedule_deliberation(report_id_str, self._settings)

        if self._cache:
            await self._cache.set_json(f"research:last:{t}", report, ttl_seconds=120)

        log.info(
            "pipeline.complete",
            run_id=run_id,
            elapsed=report["_pipeline_meta"]["elapsed_s"],
            unique_articles=len(unique),
            clusters=len(clusters),
        )
        await prog("done", "Complete")
        return report

    async def history(self, ticker: str, limit: int = 10) -> list[dict[str, Any]]:
        return await self._history.list_by_ticker(ticker.upper(), limit)

    async def analogs(self, ticker: str, event_type: str, limit: int = 5) -> list[dict[str, Any]]:
        return await self._analogs.fetch_analogs(ticker.upper(), event_type, limit)
