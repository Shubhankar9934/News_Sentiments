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
from app.db.repositories.analog_repository import AnalogRepository
from app.db.repositories.history_repository import HistoryRepository
from app.db.repositories.persistence_repository import PersistenceRepository
from app.services.cache.redis_cache import RedisCache
from app.services.collectors.news_collector import NewsCollectorService
from app.services.compression.narrative import NarrativeCompressionService
from app.services.embeddings.cleaner import NewsCleanerService
from app.services.event_extraction.rules import EventExtractionService
from app.services.impact_scoring.scorer import EventImpactScoringService
from app.services.deliberation.llm_clients.registry import ALL_DIL_MODEL_KEYS
from app.services.llm.claude_report import ClaudeReportService
from app.services.market.polygon import MarketDataService
from app.services.qdrant.store import QdrantStoreService
from app.services.sentiment.finbert import SentimentService

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
        self._analogs = AnalogRepository(session)

    async def run(
        self,
        ticker: str,
        days: int = 7,
        *,
        persist: bool = True,
        on_progress: ProgressCb | None = None,
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
        clusters = compressor.compress(with_impact)

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

        article_evidence = [
            {
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
            for a in sorted(unique, key=lambda x: x.published_at, reverse=True)[:60]
        ]

        report["_pipeline_meta"] = {
            "run_id": run_id,
            "raw_articles": len(raw),
            "after_dedupe": len(unique),
            "duplicates_removed": len(dupes),
            "clusters_to_claude": len(clusters),
            "sources": sorted({a.source for a in unique}),
            "volatility_regime": vol_regime,
            "price_snapshot": price_snapshot,
            "article_evidence": article_evidence,
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

        report["deliberation_layer"] = {
            "status": "pending",
            "run_id": run_id,
            "started_at": datetime.now(UTC).isoformat(),
            "models_requested": list(ALL_DIL_MODEL_KEYS),
        }

        report_id_str: str | None = None
        if persist:
            report_id = await self._persist.persist_report(t, f"{days}d", report)
            report_id_str = str(report_id)
            report["_pipeline_meta"]["report_id"] = report_id_str

            if self._settings.dil_enabled and report_id_str:
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
        return await self._analogs.fetch_similar_events(ticker.upper(), event_type, limit)
