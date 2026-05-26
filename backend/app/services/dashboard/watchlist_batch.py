"""Sequential per-ticker batch runner for the Reverse BWB dashboard.

This is the single orchestrator for all watchlist refreshes. It is
invoked from two places:

    1. App lifespan, when ``settings.watchlist_auto_run_on_startup`` is
       true. ``asyncio.create_task(batch.run_once())`` is scheduled so
       the server can start accepting requests while the batch runs.
    2. The ``POST /api/v1/dashboard/refresh`` and per-ticker refresh
       endpoints.

Per-ticker jobs are processed **one at a time** from an in-memory queue.
Multiple re-run clicks enqueue tickers; the worker drains the queue
sequentially. Per-ticker failure isolation: any exception from the
pipeline, summarizer, opportunity generator or DB write is caught, the
ticker is marked ``status='failed'`` via ``DashboardRepository.mark_failed``,
and the worker advances to the next queued ticker.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from redis.asyncio import Redis

from app.core.config import Settings
from app.db.repositories.dashboard_repository import DashboardRepository
from app.db.session import SessionLocal
from app.services.cache.redis_cache import RedisCache
from app.services.dashboard.opportunity_generator import (
    IbkrOpportunitySource,
    OpportunitySource,
    PlaceholderOpportunitySource,
    default_opportunity_source,
)
from app.services.dashboard.reverse_bwb_summarizer import (
    ReverseBwbSummarizer,
    ReverseBwbSummaryError,
)
from app.services.dashboard.schemas import (
    AssessmentConsensus,
    ReverseBwbSummary,
    WatchlistBatchStatus,
)
from app.services.dashboard.summary_projector import (
    fallback_decision_from_consensus,
    project_assessment_consensus,
)
from app.services.dashboard.watchlist import (
    ALL_WATCHLIST_TICKERS,
    WATCHLIST_TIERS,
    is_watchlist_ticker,
)
from app.services.deliberation.orchestrator import DeliberationOrchestrator
from app.services.deliberation.schemas import DeliberationLayer
from app.services.explainability import assemble_explainability
from app.services.orchestration.pipeline import ResearchPipelineService

if TYPE_CHECKING:
    from fastapi import FastAPI

log = structlog.get_logger(__name__)


@asynccontextmanager
async def _session_scope():
    async with SessionLocal() as session:
        yield session


class WatchlistBatchService:
    """Owns the in-process batch state + sequential refresh queue."""

    def __init__(
        self,
        settings: Settings,
        *,
        qdrant: Any | None = None,
        summarizer: ReverseBwbSummarizer | None = None,
        opportunity_source: OpportunitySource | None = None,
        ibkr_connection: Any | None = None,
        ibkr_opp_service: Any | None = None,
        quote_cache: Any | None = None,
    ) -> None:
        self._settings = settings
        self._qdrant = qdrant
        self._summarizer = summarizer or ReverseBwbSummarizer(settings)
        self._opportunity_source = opportunity_source or default_opportunity_source()
        # IBKR live data references — used to dynamically pick source at refresh time
        self._ibkr_connection = ibkr_connection
        self._ibkr_opp_service = ibkr_opp_service
        self._quote_cache = quote_cache
        self._state = WatchlistBatchStatus(total=len(ALL_WATCHLIST_TICKERS))
        self._queue: list[str] = []
        self._queue_lock = asyncio.Lock()
        self._worker_task: asyncio.Task[None] | None = None
        self._idle_event = asyncio.Event()
        self._idle_event.set()
        self._await_full_batch = False

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_app_state(cls, app: "FastAPI", settings: Settings) -> "WatchlistBatchService":
        existing = getattr(app.state, "watchlist_batch", None)
        if isinstance(existing, cls):
            return existing

        # Wire in IBKR live-data references so _refresh_ticker can dynamically
        # pick between IbkrOpportunitySource and PlaceholderOpportunitySource.
        ibkr_connection = getattr(app.state, "ibkr", None)
        ibkr_opp_service = getattr(app.state, "opp_service", None)
        quote_cache = getattr(app.state, "quote_cache", None)

        instance = cls(
            settings=settings,
            qdrant=getattr(app.state, "qdrant", None),
            summarizer=ReverseBwbSummarizer(settings),
            opportunity_source=PlaceholderOpportunitySource(),  # default fallback
            ibkr_connection=ibkr_connection,
            ibkr_opp_service=ibkr_opp_service,
            quote_cache=quote_cache,
        )
        app.state.watchlist_batch = instance
        return instance

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------

    @property
    def status(self) -> WatchlistBatchStatus:
        # Return a copy so callers can serialize without racing the writer.
        return self._state.model_copy(deep=True)

    @property
    def is_running(self) -> bool:
        return (
            self._state.state == "running"
            or self._state.current_ticker is not None
            or len(self._queue) > 0
            or (self._worker_task is not None and not self._worker_task.done())
        )

    # ------------------------------------------------------------------
    # Queue entrypoints
    # ------------------------------------------------------------------

    async def run_once(self) -> WatchlistBatchStatus:
        """Enqueue every watchlist ticker in tier order and wait until done."""

        self._await_full_batch = True
        if self._state.started_at is None:
            self._state.started_at = datetime.now(UTC)

        for tier in WATCHLIST_TIERS:
            for entry in tier.tickers:
                await self.enqueue_ticker(entry.symbol)

        await self._idle_event.wait()

        self._state.finished_at = datetime.now(UTC)
        self._state.state = (
            "failed"
            if self._state.failed and not self._state.completed
            else "completed"
        )
        self._await_full_batch = False
        log.info(
            "watchlist.refresh.done",
            completed=len(self._state.completed),
            failed=len(self._state.failed),
        )
        return self.status

    async def run_single(self, ticker: str) -> WatchlistBatchStatus:
        """Enqueue a single watchlist ticker refresh (per-card re-run)."""

        await self.enqueue_ticker(ticker)
        return self.status

    async def enqueue_ticker(self, ticker: str) -> WatchlistBatchStatus:
        """Add a ticker to the refresh queue if it is not already pending."""

        upper = ticker.upper()
        if not is_watchlist_ticker(upper):
            raise ValueError(f"{upper!r} is not on the dashboard watchlist")

        async with self._queue_lock:
            if upper == self._state.current_ticker:
                return self.status
            if upper in self._queue:
                return self.status

            self._queue.append(upper)
            self._sync_queued_state()

            if self._state.started_at is None:
                self._state.started_at = datetime.now(UTC)
            self._state.state = "running"
            self._idle_event.clear()
            self._ensure_worker()

        log.info("watchlist.ticker.enqueued", ticker=upper, queue_depth=len(self._queue))
        return self.status

    async def wait_idle(self) -> None:
        """Block until the worker has drained the queue (tests / startup batch)."""

        await self._idle_event.wait()

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    def _sync_queued_state(self) -> None:
        current = self._state.current_ticker
        self._state.queued = [t for t in self._queue if t != current]

    async def _worker_loop(self) -> None:
        try:
            while True:
                async with self._queue_lock:
                    if not self._queue:
                        self._state.current_ticker = None
                        break
                    ticker = self._queue.pop(0)
                    self._sync_queued_state()
                    self._state.current_ticker = ticker

                log.info("watchlist.ticker.start", ticker=ticker)
                await self._refresh_ticker(ticker)
        finally:
            async with self._queue_lock:
                if not self._queue:
                    self._state.current_ticker = None
                self._sync_queued_state()
                if not self._queue:
                    self._state.finished_at = datetime.now(UTC)
                    if not self._await_full_batch:
                        self._state.state = "idle"
                    self._idle_event.set()
            self._worker_task = None

    # ------------------------------------------------------------------
    # Internal per-ticker step
    # ------------------------------------------------------------------

    async def _refresh_ticker(self, ticker: str) -> None:
        """End-to-end refresh for a ticker, with failure isolation.

        Pipeline → desk analyses → Assessment Team (owns all card
        fields except decision) → Decision Council (owns decision) →
        single canonical ``ReverseBwbSummary`` write. The async
        deliberation kick-off is suppressed because we run the
        orchestrator inline.
        """

        # Drop any stale entry from a prior refresh so the lists reflect the
        # latest outcome only.
        if ticker in self._state.completed:
            self._state.completed.remove(ticker)
        if ticker in self._state.failed:
            self._state.failed.remove(ticker)

        try:
            redis_cache = await self._build_redis_cache()
            try:
                async with _session_scope() as session:
                    pipeline = ResearchPipelineService(
                        session=session,
                        settings=self._settings,
                        qdrant=self._qdrant,
                        cache=redis_cache,
                        quote_cache=self._quote_cache,  # IBKR live price injection
                    )
                    report = await pipeline.run(
                        ticker,
                        days=self._settings.watchlist_run_days,
                        persist=True,
                        schedule_dil=False,
                    )

                    layer: DeliberationLayer | None = None
                    if self._settings.dil_enabled:
                        try:
                            layer = await DeliberationOrchestrator(
                                self._settings
                            ).run(report, ticker)
                            report["deliberation_layer"] = layer.to_dict()
                        except Exception as exc:  # never break the batch
                            log.warning(
                                "watchlist.deliberation_failed",
                                ticker=ticker,
                                error=str(exc),
                            )

                    summary, assessment_dict, council_dict = self._build_summary(
                        ticker, report, layer
                    )

                    # Assemble the explainability layer AFTER both the
                    # deliberation layer and the final summary exist. The
                    # card schema is unaffected — this writes to
                    # report_json["explainability"] + the dedicated
                    # nullable JSONB column only.
                    explainability_payload: dict[str, Any] | None = None
                    if self._settings.explainability_enabled:
                        try:
                            explain_layer = assemble_explainability(
                                ticker=ticker,
                                report=report,
                                deliberation_layer=(
                                    layer.to_dict() if layer is not None else None
                                ),
                                summary=summary,
                            )
                            explainability_payload = explain_layer.model_dump(
                                mode="json", exclude_none=True
                            )
                            report["explainability"] = explainability_payload
                        except Exception as exc:  # never break the batch
                            log.warning(
                                "watchlist.explainability_failed",
                                ticker=ticker,
                                error=str(exc),
                            )

                    # Dynamically select the opportunity source at refresh time.
                    # IbkrOpportunitySource is used when IBKR is connected and an
                    # OptionsOpportunityService is available; PlaceholderOpportunitySource
                    # is the safe fallback for disconnected/unavailable states.
                    _ibkr_live = (
                        self._ibkr_connection is not None
                        and getattr(self._ibkr_connection, "is_connected", False)
                        and self._ibkr_opp_service is not None
                    )
                    if _ibkr_live:
                        _source: OpportunitySource = IbkrOpportunitySource(
                            self._ibkr_opp_service
                        )
                        log.info(
                            "watchlist.opportunity_source",
                            ticker=ticker,
                            source="ibkr_live",
                        )
                    else:
                        _source = self._opportunity_source  # PlaceholderOpportunitySource
                        log.info(
                            "watchlist.opportunity_source",
                            ticker=ticker,
                            source="placeholder",
                            ibkr_connected=self._ibkr_connection is not None
                            and getattr(self._ibkr_connection, "is_connected", False),
                        )
                    opportunities = await _source.generate(ticker, report)

                    # Write opportunity audit to the pipeline's txt folder
                    _audit_folder = (report.get("_pipeline_meta") or {}).get("audit_folder")
                    if _audit_folder:
                        try:
                            import json
                            import os
                            _opp_data = {
                                "source": "ibkr_live" if _ibkr_live else "placeholder",
                                "ibkr_connected": _ibkr_live,
                                "calls_count": len(opportunities.calls),
                                "puts_count": len(opportunities.puts),
                                "calls": [
                                    {
                                        "combo": o.combo,
                                        "expiry": o.expiry,
                                        "premium": o.premium,
                                        "margin": o.margin,
                                        "liquidity": o.liquidity,
                                    }
                                    for o in opportunities.calls
                                ],
                                "puts": [
                                    {
                                        "combo": o.combo,
                                        "expiry": o.expiry,
                                        "premium": o.premium,
                                        "margin": o.margin,
                                        "liquidity": o.liquidity,
                                    }
                                    for o in opportunities.puts
                                ],
                            }
                            _opp_path = os.path.join(_audit_folder, "09_opportunities.txt")
                            with open(_opp_path, "w", encoding="utf-8") as _f:
                                _f.write(
                                    f"{'=' * 80}\n"
                                    f"PIPELINE AUDIT — OPPORTUNITIES\n"
                                    f"Ticker : {ticker}\n"
                                    f"{'=' * 80}\n\n"
                                )
                                _f.write(json.dumps(_opp_data, indent=2, default=str))
                        except Exception as _ae:
                            log.debug("watchlist.audit_opp_write_failed", error=str(_ae))

                    research_report_id = self._extract_research_report_id(report)
                    if research_report_id is not None:
                        try:
                            from app.db.repositories.deliberation_repository import (
                                DeliberationRepository,
                            )

                            await DeliberationRepository(session).replace_report_json(
                                research_report_id,
                                report,
                                commit=False,
                            )
                        except Exception as exc:  # never break the batch on sync drift
                            log.warning(
                                "watchlist.research_report_sync_failed",
                                ticker=ticker,
                                error=str(exc),
                            )
                    await DashboardRepository(session).save_snapshot(
                        ticker=ticker,
                        report_json=report,
                        summary=summary,
                        opportunities=opportunities,
                        research_report_id=research_report_id,
                        assessment_layer=assessment_dict,
                        council_layer=council_dict,
                        explainability=explainability_payload,
                    )
            finally:
                await self._dispose_redis_cache(redis_cache)
            self._state.completed.append(ticker)
            log.info("watchlist.ticker.completed", ticker=ticker)
        except Exception as exc:  # NEVER stop the batch
            log.exception("watchlist.ticker_failed", ticker=ticker)
            self._state.failed.append(ticker)
            self._state.last_error = f"{ticker}: {exc}"[:1000]
            await self._safe_mark_failed(ticker, str(exc))

    def _build_summary(
        self,
        ticker: str,
        report: dict[str, Any],
        layer: DeliberationLayer | None,
    ) -> tuple[ReverseBwbSummary, dict[str, Any] | None, dict[str, Any] | None]:
        """Merge Assessment Team body + Decision Council verdict.

        Falls back to the deterministic projector when the Assessment
        Team consensus is unavailable, and to the deterministic
        decision rule when the Council consensus is unavailable.
        """

        assessment_dict: dict[str, Any] | None = None
        council_dict: dict[str, Any] | None = None
        consensus: AssessmentConsensus | None = None

        if layer is not None:
            assessment_dict = layer.assessment_layer
            council_dict = layer.council_layer
            if assessment_dict:
                raw_consensus = assessment_dict.get("consensus")
                if raw_consensus:
                    try:
                        consensus = AssessmentConsensus.model_validate(
                            raw_consensus
                        )
                    except Exception as exc:  # pragma: no cover
                        log.warning(
                            "watchlist.consensus_parse_failed",
                            ticker=ticker,
                            error=str(exc),
                        )
                        consensus = None

        if consensus is None:
            consensus = project_assessment_consensus(ticker, report)

        decision: str | None = None
        if layer is not None and layer.mapped_decision:
            decision = layer.mapped_decision
        elif council_dict:
            raw = (council_dict.get("consensus") or {}).get("decision")
            if raw:
                from app.services.deliberation.decision_labels import (
                    council_to_dashboard,
                )

                decision = council_to_dashboard(raw)
        if not decision:
            decision = fallback_decision_from_consensus(consensus)

        summary = ReverseBwbSummary(
            ticker=ticker.upper(),
            decision=decision,  # type: ignore[arg-type]
            credit_safety_score=consensus.credit_safety_score,
            risk=consensus.risk,
            confidence=consensus.confidence,
            today_outlook=consensus.today_outlook,
            next_3d_outlook=consensus.next_3d_outlook,
            chance_up_2_3_pct=consensus.chance_up_2_3_pct,
            chance_down_2_3_pct=consensus.chance_down_2_3_pct,
            expected_range_today=consensus.expected_range_today,
            expected_range_next_3d=consensus.expected_range_next_3d,
            danger_zone=consensus.danger_zone,
            pin_risk=consensus.pin_risk,
            event_risk=consensus.event_risk,
            iv_quality=consensus.iv_quality,
            liquidity=consensus.liquidity,
            actual_dynamics_summary=list(consensus.actual_dynamics_summary),
        )
        return summary, assessment_dict, council_dict

    async def _safe_mark_failed(self, ticker: str, error_message: str) -> None:
        try:
            async with _session_scope() as session:
                await DashboardRepository(session).mark_failed(ticker, error_message)
        except Exception:  # pragma: no cover - DB failure during failure path
            log.exception("watchlist.mark_failed_failed", ticker=ticker)

    async def _build_redis_cache(self) -> RedisCache | None:
        if not self._settings.redis_url:
            return None
        try:
            redis_client = Redis.from_url(self._settings.redis_url, decode_responses=True)
            await redis_client.ping()
            cache = RedisCache(redis_client)
            cache.__watchlist_owned_client = redis_client  # type: ignore[attr-defined]
            return cache
        except Exception as exc:
            log.warning("watchlist.redis_unavailable", error=str(exc))
            return None

    async def _dispose_redis_cache(self, cache: RedisCache | None) -> None:
        if cache is None:
            return
        client = getattr(cache, "__watchlist_owned_client", None)
        if client is None:
            return
        try:
            await client.aclose()
        except Exception:  # pragma: no cover
            log.debug("watchlist.redis_close_failed", exc_info=True)

    @staticmethod
    def _extract_research_report_id(report: dict[str, Any]) -> Any | None:
        meta = report.get("_pipeline_meta") or {}
        candidate = meta.get("report_id") or report.get("report_id")
        if candidate is None:
            return None
        try:
            import uuid

            return uuid.UUID(str(candidate))
        except (TypeError, ValueError):
            return None
