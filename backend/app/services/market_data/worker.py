"""Background worker that drives the live market-data pipeline.

Three independently-scheduled asyncio tasks:

    1. ``_price_loop`` (every ``MARKET_DATA_PRICE_FLUSH_MS``, default 1 s)
       - Drains every dirty ``ib_async.Ticker`` snapshot.
       - Writes to ``QuoteCache`` (in-process dict + Redis) immediately.
       - Feeds ticks into ``CandleAggregator`` for 1-minute OHLCV.
       - Publishes tick messages to :class:`MarketDataPubSub` (or Redis
         channel when ``REDIS_PUBSUB_ENABLED=true``) for WebSocket fanout.
       - No-ops when IBKR is disconnected.

    2. ``_db_flush_loop`` (every ``MARKET_DATA_DB_FLUSH_S``, default 5 s)
       - Reads all quotes from the in-process cache and batch-UPSERTs to
         ``ticker_market_data``.
       - DB is NO LONGER in the tick hot path — WebSocket publish fires
         immediately after the cache write.

    3. ``_candle_flush_loop`` (every 60 s)
       - Drains closed 1-minute OHLCV candles from ``CandleAggregator``
         and UPSERTs them to ``market_candles_1m``.

The opportunity recalculation loop has been extracted to
:class:`OpportunityEngineWorker` in ``opportunity_worker.py`` so the two
concerns scale independently.

Both workers are kicked off from ``app.main.lifespan`` only when
``IBKR_ENABLED=true`` and stop cleanly on shutdown.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time as dtime
from decimal import Decimal

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import Settings
from app.db.session import SessionLocal
from app.services.market_data import metrics as md_metrics
from app.services.market_data.candle_aggregator import Candle1m, CandleAggregator
from app.services.market_data.ibkr_connection import IbkrConnection
from app.services.market_data.market_data_service import MarketDataService
from app.services.market_data.pubsub import MarketDataPubSub, TickMessage
from app.services.market_data.quote_cache import QuoteCache
from app.services.market_data.repository import MarketDataRepository
from app.services.market_data.schemas import LiveQuote

log = structlog.get_logger(__name__)


class MarketDataWorker:
    """Owns the price loop, DB-flush loop, and candle-flush loop.

    The opportunity recalculation loop lives in ``OpportunityEngineWorker``
    and is started separately from ``app.main.lifespan``.
    """

    def __init__(
        self,
        settings: Settings,
        connection: IbkrConnection,
        market_data: MarketDataService,
        watchlist: tuple[str, ...],
        pubsub: MarketDataPubSub | None = None,
        quote_cache: QuoteCache | None = None,
        redis_bridge: object | None = None,  # RedisPubSubBridge | None
    ) -> None:
        self._settings = settings
        self._connection = connection
        self._market_data = market_data
        self._watchlist = tuple(t.upper() for t in watchlist)
        self._pubsub = pubsub or MarketDataPubSub(
            tick_batch_ms=settings.ws_tick_batch_ms,
        )
        self._quote_cache = quote_cache or QuoteCache(None, ttl_s=30)
        self._redis_bridge = redis_bridge
        self._candle_agg = CandleAggregator()

        self._price_task: asyncio.Task[None] | None = None
        self._db_flush_task: asyncio.Task[None] | None = None
        self._candle_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------- properties
    @property
    def pubsub(self) -> MarketDataPubSub:
        return self._pubsub

    # ------------------------------------------------------------------ start/stop
    async def start(self) -> None:
        """Begin all loops + pubsub. Idempotent."""
        await self._pubsub.start()
        if self._price_task is None or self._price_task.done():
            self._stop_event.clear()
            self._price_task = asyncio.create_task(
                self._price_loop(), name="market_data.price_loop"
            )
        if self._db_flush_task is None or self._db_flush_task.done():
            self._db_flush_task = asyncio.create_task(
                self._db_flush_loop(), name="market_data.db_flush"
            )
        if self._candle_task is None or self._candle_task.done():
            self._candle_task = asyncio.create_task(
                self._candle_flush_loop(), name="market_data.candle_flush"
            )
        log.info(
            "market_data.worker.started",
            watchlist=list(self._watchlist),
            price_flush_ms=self._settings.market_data_price_flush_ms,
            db_flush_s=self._settings.market_data_db_flush_s,
        )

    async def stop(self) -> None:
        """Cancel all loops and clear in-memory subscriptions."""
        self._stop_event.set()
        for task in (self._price_task, self._db_flush_task, self._candle_task):
            if task is None or task.done():
                continue
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._price_task = None
        self._db_flush_task = None
        self._candle_task = None

        await self._pubsub.stop()

        try:
            await self._market_data.cancel_subscriptions()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("market_data.cancel_subscriptions_failed", error=str(exc))

        try:
            async with SessionLocal() as session:
                repo = MarketDataRepository(session)
                await repo.mark_disconnected(self._watchlist)
        except Exception as exc:
            log.warning("market_data.mark_disconnected_failed", error=str(exc))
        log.info("market_data.worker.stopped")

    # ------------------------------------------------------------------ helpers
    def _make_repository(self) -> tuple[MarketDataRepository, object]:
        session_ctx = SessionLocal()
        repo = MarketDataRepository(session_ctx)
        return repo, session_ctx

    async def _ensure_subscriptions(self) -> bool:
        if not self._connection.is_connected:
            return False
        return await self._market_data.subscribe_quotes(self._watchlist)

    # ------------------------------------------------------------------ price loop
    async def _price_loop(self) -> None:
        flush_seconds = max(0.1, self._settings.market_data_price_flush_ms / 1000.0)
        log.info("market_data.price_loop.started", flush_seconds=flush_seconds)
        while not self._stop_event.is_set():
            try:
                if not self._connection.is_connected:
                    await self._sleep_or_stop(flush_seconds)
                    continue

                await self._ensure_subscriptions()

                quotes = await self._market_data.drain_quotes()
                if quotes:
                    for q in quotes:
                        await self._quote_cache.set(q)
                        if q.last_price is not None:
                            self._candle_agg.on_tick(
                                q.ticker,
                                q.last_price,
                                q.volume,
                                q.updated_at or datetime.now(UTC),
                            )
                    await self._publish_ticks(quotes)
                    log.debug("market_data.price_flushed", count=len(quotes))

                await self._mark_stale_if_needed()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("market_data.price_loop.error", error=str(exc))

            await self._sleep_or_stop(flush_seconds)
        log.info("market_data.price_loop.stopped")

    async def _publish_ticks(self, quotes: list[LiveQuote]) -> None:
        for q in quotes:
            msg = TickMessage(
                ticker=q.ticker.upper(),
                last_price=q.last_price,
                bid=q.bid,
                ask=q.ask,
                change_abs=q.change_abs,
                change_pct=q.change_pct,
                volume=q.volume,
                feed_status=q.feed_status,
                updated_at=q.updated_at,
            )
            if self._settings.redis_pubsub_enabled and self._redis_bridge is not None:
                await self._redis_bridge.publish_tick(msg)  # type: ignore[attr-defined]
            else:
                await self._pubsub.publish_tick(msg)
            md_metrics.ws_messages_total.labels(type="tick").inc()

    async def _mark_stale_if_needed(self) -> None:
        threshold = self._settings.market_data_stale_threshold_s
        if threshold <= 0:
            return
        now = datetime.now(UTC)
        cutoff = now.timestamp() - threshold
        slot_state = self._market_data._subs.slots  # type: ignore[attr-defined]
        stale_quotes: list[LiveQuote] = []
        for sym, slot in slot_state.items():
            if slot.last_seen_at is None:
                continue
            if slot.last_seen_at.timestamp() < cutoff:
                stale_quotes.append(
                    LiveQuote(
                        ticker=sym,
                        last_price=None,
                        prev_close=slot.prev_close,
                        feed_status="stale",
                        updated_at=now,
                    )
                )
        if stale_quotes:
            async with SessionLocal() as session:
                from sqlalchemy import update

                from app.db.models.tables import TickerMarketDataModel

                for q in stale_quotes:
                    await session.execute(
                        update(TickerMarketDataModel)
                        .where(TickerMarketDataModel.ticker == q.ticker)
                        .values(feed_status="stale", updated_at=q.updated_at)
                    )
                await session.commit()

    # ------------------------------------------------------------------ DB flush loop
    async def _db_flush_loop(self) -> None:
        flush_s = max(1, self._settings.market_data_db_flush_s)
        log.info("market_data.db_flush_loop.started", flush_s=flush_s)
        while not self._stop_event.is_set():
            await self._sleep_or_stop(flush_s)
            try:
                quotes = list(self._quote_cache.get_all().values())
                if quotes:
                    async with SessionLocal() as session:
                        repo = MarketDataRepository(session)
                        await repo.upsert_quotes_bulk(quotes)
                    log.debug("market_data.db_flush.wrote", count=len(quotes))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("market_data.db_flush.error", error=str(exc))
        log.info("market_data.db_flush_loop.stopped")

    # ------------------------------------------------------------------ candle flush loop
    async def _candle_flush_loop(self) -> None:
        log.info("market_data.candle_flush_loop.started")
        while not self._stop_event.is_set():
            await self._sleep_or_stop(60.0)
            try:
                now = datetime.now(UTC)
                candles = self._candle_agg.drain_closed(now)
                if candles:
                    async with SessionLocal() as session:
                        await self._upsert_candles(session, candles)
                    log.debug("market_data.candle_flush.wrote", count=len(candles))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("market_data.candle_flush.error", error=str(exc))
        log.info("market_data.candle_flush_loop.stopped")

    async def _upsert_candles(self, session: object, candles: list[Candle1m]) -> None:
        from sqlalchemy.ext.asyncio import AsyncSession

        from app.db.models.tables import MarketCandle1mModel

        rows = [
            {
                "ticker": c.ticker,
                "ts": c.ts,
                "open": Decimal(repr(c.open)),
                "high": Decimal(repr(c.high)),
                "low": Decimal(repr(c.low)),
                "close": Decimal(repr(c.close)),
                "volume": c.volume,
            }
            for c in candles
        ]
        stmt = pg_insert(MarketCandle1mModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "ts"],
            set_={
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        assert isinstance(session, AsyncSession)
        await session.execute(stmt)
        await session.commit()

    # ----------------------------------------------------------------- timing
    async def _sleep_or_stop(self, seconds: float) -> None:
        if seconds <= 0:
            return
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return


def _is_at_or_after_market_open(now: datetime) -> bool:
    """Heuristic US market-open check (09:30 ET / 13:30 UTC, weekdays).

    The check uses UTC directly to avoid pulling pytz. The boundary is
    a soft signal — we only need it to be approximately correct since
    the worker also has the 15-minute stale trigger as a backstop.
    """
    if now.weekday() >= 5:
        return False
    return now.timetz().replace(tzinfo=None) >= dtime(13, 30)


__all__ = ["MarketDataWorker"]
