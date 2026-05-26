"""Opportunity engine worker — independent from the price-data worker.

Extracted from ``MarketDataWorker`` so the two can start, scale, and
fail independently.

One asyncio task:

    ``_opportunity_loop`` (every ``MARKET_DATA_OPP_INTERVAL_S``, default 45 s)
       - Iterates the watchlist sequentially (IBKR pacing safety).
       - Decides whether each ticker should recalc this cycle:
           * underlying moved > ``OPP_RECALC_PRICE_PCT``,
           * more than ``OPP_RECALC_MAX_AGE_S`` since last recalc,
           * first tick after market open.
       - When recalc fires, calls ``OptionsOpportunityService.generate``,
         atomically replaces ``ticker_live_option_opportunities`` rows per
         side, AND appends every row to ``ticker_option_opportunity_history``.
       - Publishes one ``opportunity_version`` message per (ticker, side).
       - Catches per-ticker exceptions so one bad symbol can't kill the loop.

Reads the latest quote from ``QuoteCache.get_local()`` (zero-latency
in-process dict populated by ``MarketDataWorker._price_loop``).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, time as dtime

import structlog

from app.core.config import Settings
from app.db.session import SessionLocal
from app.services.market_data import metrics as md_metrics
from app.services.market_data.options_opportunity_service import (
    OpportunityResult,
    OptionsOpportunityService,
)
from app.services.market_data.pubsub import (
    MarketDataPubSub,
    OpportunityVersionMessage,
)
from app.services.market_data.quote_cache import QuoteCache
from app.services.market_data.repository import MarketDataRepository

log = structlog.get_logger(__name__)


@dataclass
class _RecalcState:
    """Per-ticker tracking for the event-driven recalc trigger."""

    last_recalc_at: datetime | None = None
    last_recalc_price: float | None = None
    last_recalc_iv: float | None = None
    last_market_open_date: str | None = None


class OpportunityEngineWorker:
    """Runs the opportunity recalculation loop independently of the price loop."""

    def __init__(
        self,
        settings: Settings,
        opp_service: OptionsOpportunityService,
        pubsub: MarketDataPubSub,
        quote_cache: QuoteCache,
        watchlist: tuple[str, ...],
        redis_bridge: object | None = None,  # RedisPubSubBridge | None
    ) -> None:
        self._settings = settings
        self._opp_service = opp_service
        self._pubsub = pubsub
        self._quote_cache = quote_cache
        self._watchlist = tuple(t.upper() for t in watchlist)
        self._redis_bridge = redis_bridge

        self._opp_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        self._recalc_state: dict[str, _RecalcState] = {
            ticker: _RecalcState() for ticker in self._watchlist
        }
        self._max_recalcs_per_cycle = max(1, len(self._watchlist))

    # ---------------------------------------------------------------- properties
    @property
    def opp_service(self) -> OptionsOpportunityService:
        return self._opp_service

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        """Begin the opportunity loop. Idempotent."""
        if self._opp_task is None or self._opp_task.done():
            self._stop_event.clear()
            self._opp_task = asyncio.create_task(
                self._opportunity_loop(), name="market_data.opportunity_loop"
            )
        log.info(
            "opportunity_worker.started",
            watchlist=list(self._watchlist),
            opp_interval_s=self._settings.market_data_opp_interval_s,
            recalc_max_age_s=self._settings.opp_recalc_max_age_s,
        )

    async def stop(self) -> None:
        """Signal and await the opportunity loop."""
        self._stop_event.set()
        if self._opp_task is not None and not self._opp_task.done():
            self._opp_task.cancel()
            try:
                await self._opp_task
            except (asyncio.CancelledError, Exception):
                pass
        self._opp_task = None
        log.info("opportunity_worker.stopped")

    # ---------------------------------------------------------------- opportunity loop
    async def _opportunity_loop(self) -> None:
        interval = max(5, int(self._settings.market_data_opp_interval_s))
        log.info("market_data.opp_loop.started", interval_s=interval)

        # Stagger the first run so the price loop populates last_price first.
        await self._sleep_or_stop(3.0)

        while not self._stop_event.is_set():
            try:
                await self._opportunity_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("market_data.opp_loop.error", error=str(exc))
            await self._sleep_or_stop(interval)
        log.info("market_data.opp_loop.stopped")

    async def _opportunity_cycle(self) -> None:
        recalced = 0
        for ticker in self._watchlist:
            if self._stop_event.is_set():
                return
            if recalced >= self._max_recalcs_per_cycle:
                break
            try:
                did_recalc = await self._maybe_recalc_one_ticker(ticker)
            except Exception as exc:
                log.warning(
                    "market_data.opp_loop.ticker_failed",
                    ticker=ticker,
                    error=str(exc),
                )
                continue
            if did_recalc:
                recalced += 1

    async def _maybe_recalc_one_ticker(self, ticker: str) -> bool:
        """Decide and (if needed) execute one ticker's recalc.

        Reads price from QuoteCache (zero-latency in-process dict) with a
        DB fallback for the first cycle before any ticks have arrived.

        Returns True if a recalc was actually performed.
        """
        # Cache-first price lookup.
        quote = self._quote_cache.get_local(ticker)
        last_price: float | None = quote.last_price if quote is not None else None

        if last_price is None:
            # Fallback to DB for the first cycle (cache not yet populated).
            async with SessionLocal() as session:
                repo = MarketDataRepository(session)
                db_quote = await repo.get_quote(
                    ticker,
                    stale_threshold_s=self._settings.market_data_stale_threshold_s,
                )
                last_price = db_quote.last_price if db_quote is not None else None

        trigger = self._decide_recalc_trigger(ticker, last_price=last_price)
        if trigger is None:
            return False

        result = await self._opp_service.generate(ticker, last_price=last_price)
        if result.skipped_reason:
            log.info(
                "market_data.opp_loop.skipped",
                ticker=ticker,
                reason=result.skipped_reason,
                trigger=trigger,
            )
            # Update last_recalc_at on every failure so the stale trigger
            # doesn't loop every 45 s once the threshold is exceeded.
            # market_open fires independently at 13:30 UTC regardless.
            state = self._recalc_state.setdefault(ticker, _RecalcState())
            state.last_recalc_at = datetime.now(UTC)
            return False

        await self._persist_and_publish(result, trigger=trigger)
        self._update_recalc_state(ticker, result=result)
        return True

    def _decide_recalc_trigger(
        self,
        ticker: str,
        *,
        last_price: float | None,
    ) -> str | None:
        """Return the trigger name, or None to skip this cycle.

        Triggers (in priority order):
            * ``startup``       — first cycle after process start, during market hours only
            * ``market_open``   — first cycle after the trading session opens (13:30 UTC)
            * ``price_move``    — underlying moved > OPP_RECALC_PRICE_PCT
            * ``stale``         — >= OPP_RECALC_MAX_AGE_S since last recalc

        Pre-market guard: ``startup``, ``price_move`` and ``stale`` are suppressed
        outside market hours. IBKR returns no option bid/ask pre-market so these
        cycles waste pacing quota and always return ``no_priced_candidates``.
        ``market_open`` fires at exactly 13:30 UTC and is always the first real
        recalc of each session.
        """
        state = self._recalc_state.setdefault(ticker, _RecalcState())
        now = datetime.now(UTC)
        market_open = _is_at_or_after_market_open(now)

        if state.last_recalc_at is None:
            if not market_open:
                # Pre-market first cycle: mark as attempted so the stale trigger
                # doesn't also fire; the market_open trigger handles the real recalc.
                state.last_recalc_at = datetime.now(UTC)
                log.info(
                    "opportunity_worker.pre_market_skip",
                    ticker=ticker,
                    reason="startup_suppressed_pre_market",
                )
                return None
            return "startup"

        today = now.date().isoformat()
        if market_open and state.last_market_open_date != today:
            return "market_open"

        # price_move and stale are only meaningful during market hours.
        if not market_open:
            return None

        if (
            last_price is not None
            and state.last_recalc_price
            and state.last_recalc_price > 0
        ):
            pct = (
                abs(last_price - state.last_recalc_price)
                / state.last_recalc_price
                * 100.0
            )
            if pct >= self._settings.opp_recalc_price_pct:
                return "price_move"

        age = (now - state.last_recalc_at).total_seconds()
        if age >= self._settings.opp_recalc_max_age_s:
            return "stale"

        return None

    def _update_recalc_state(self, ticker: str, *, result: OpportunityResult) -> None:
        state = self._recalc_state.setdefault(ticker, _RecalcState())
        state.last_recalc_at = datetime.now(UTC)
        if result.underlying_price is not None:
            state.last_recalc_price = result.underlying_price
        if result.atm_iv is not None:
            state.last_recalc_iv = result.atm_iv
        state.last_market_open_date = datetime.now(UTC).date().isoformat()

    async def _persist_and_publish(
        self,
        result: OpportunityResult,
        *,
        trigger: str,
    ) -> None:
        async with SessionLocal() as session:
            repo = MarketDataRepository(session)
            await repo.replace_opportunities(result.ticker, "call", result.calls)
            await repo.replace_opportunities(result.ticker, "put", result.puts)
            await repo.append_history(result.calls + result.puts)
            await repo.commit()

        md_metrics.opportunity_version_total.labels(
            ticker=result.ticker, trigger=trigger
        ).inc()
        md_metrics.opps_persisted_total.labels(
            ticker=result.ticker, side="call"
        ).inc(len(result.calls))
        md_metrics.opps_persisted_total.labels(
            ticker=result.ticker, side="put"
        ).inc(len(result.puts))
        md_metrics.opps_history_appended_total.labels(
            ticker=result.ticker, side="call"
        ).inc(len(result.calls))
        md_metrics.opps_history_appended_total.labels(
            ticker=result.ticker, side="put"
        ).inc(len(result.puts))

        if result.opportunity_version is not None:
            for side, rows in (("call", result.calls), ("put", result.puts)):
                if not rows:
                    continue
                msg = OpportunityVersionMessage(
                    ticker=result.ticker,
                    side=side,
                    opportunity_version=result.opportunity_version,
                    count=len(rows),
                )
                if self._settings.redis_pubsub_enabled and self._redis_bridge is not None:
                    await self._redis_bridge.publish_opportunity_version(msg)  # type: ignore[attr-defined]
                else:
                    await self._pubsub.publish_opportunity_version(msg)
                md_metrics.ws_messages_total.labels(type="opportunity_version").inc()

        log.info(
            "market_data.opp_loop.refreshed",
            ticker=result.ticker,
            trigger=trigger,
            calls=len(result.calls),
            puts=len(result.puts),
            version=str(result.opportunity_version),
        )

    # ----------------------------------------------------------------- timing
    async def _sleep_or_stop(self, seconds: float) -> None:
        if seconds <= 0:
            return
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return


def _is_at_or_after_market_open(now: datetime) -> bool:
    """Heuristic US market-open check (09:30 ET / 13:30 UTC, weekdays)."""
    if now.weekday() >= 5:
        return False
    return now.timetz().replace(tzinfo=None) >= dtime(13, 30)


__all__ = ["OpportunityEngineWorker"]
