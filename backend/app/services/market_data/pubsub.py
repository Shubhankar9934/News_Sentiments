"""In-process pub/sub for the live market-data WebSocket fanout.

Two channels:

    * ``tick``                — emitted by the worker every flushed batch
                                of underlying quotes, debounced via
                                ``WS_TICK_BATCH_MS``.
    * ``opportunity_version`` — emitted when the worker persists a new
                                cycle; carries the per-side UUID so
                                clients refetch only what changed.

The class is intentionally minimal — one singleton per FastAPI process,
held on ``app.state.market_data_pubsub``. Subscribers receive copies of
every message; back-pressure is the subscriber's responsibility (drop
on full queue).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

log = structlog.get_logger(__name__)


@dataclass
class TickMessage:
    ticker: str
    last_price: float | None
    bid: float | None
    ask: float | None
    change_abs: float | None
    change_pct: float | None
    volume: int | None
    feed_status: str
    updated_at: datetime | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": "tick",
            "ticker": self.ticker,
            "last": self.last_price,
            "bid": self.bid,
            "ask": self.ask,
            "change_abs": self.change_abs,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "feed_status": self.feed_status,
            "ts": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class OpportunityVersionMessage:
    ticker: str
    side: str  # "call" | "put"
    opportunity_version: UUID
    count: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": "opportunity_version",
            "ticker": self.ticker,
            "side": self.side,
            "opportunity_version": str(self.opportunity_version),
            "count": int(self.count),
            "ts": datetime.now(UTC).isoformat(),
        }


@dataclass
class _Subscriber:
    queue: asyncio.Queue[dict[str, Any]]
    tickers: set[str] = field(default_factory=set)  # uppercased; empty = all
    types: set[str] = field(default_factory=lambda: {"tick", "opportunity_version"})


class MarketDataPubSub:
    """Fanout broker for tick / opportunity_version messages.

    Subscribers are tracked in-process. The worker calls
    :meth:`publish_tick` and :meth:`publish_opportunity_version`; the
    WebSocket route consumes via :meth:`subscribe` and forwards JSON to
    its socket.
    """

    def __init__(self, *, tick_batch_ms: int = 250, queue_max: int = 256) -> None:
        self._tick_batch_s = max(0.0, float(tick_batch_ms) / 1000.0)
        self._queue_max = max(8, int(queue_max))
        self._subscribers: list[_Subscriber] = []
        self._lock = asyncio.Lock()
        # Tick debounce buffer keyed by ticker — only the most recent
        # tick per ticker survives a batch window.
        self._tick_buffer: dict[str, TickMessage] = {}
        self._flush_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_flush = time.monotonic()
        # Counters for /health endpoints.
        self.published_ticks = 0
        self.published_versions = 0
        self.dropped_overflow = 0

    # --------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        if self._flush_task is None or self._flush_task.done():
            self._stop.clear()
            self._flush_task = asyncio.create_task(
                self._flush_loop(), name="market_data.pubsub.flush"
            )

    async def stop(self) -> None:
        self._stop.set()
        task = self._flush_task
        self._flush_task = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    # ------------------------------------------------------------------ stats
    @property
    def active_subscribers(self) -> int:
        return len(self._subscribers)

    # ------------------------------------------------------------------ pub
    async def publish_tick(self, msg: TickMessage) -> None:
        """Buffer one tick; the flush loop coalesces and fans out."""
        async with self._lock:
            self._tick_buffer[msg.ticker.upper()] = msg
        if self._tick_batch_s <= 0:
            # Synchronous mode (tests).
            await self._flush_once()

    async def publish_opportunity_version(self, msg: OpportunityVersionMessage) -> None:
        payload = msg.to_payload()
        await self._dispatch(payload)
        self.published_versions += 1

    # ----------------------------------------------------------------- sub
    async def subscribe(
        self,
        *,
        tickers: list[str] | None = None,
        types: list[str] | None = None,
    ) -> _Subscriber:
        sub = _Subscriber(
            queue=asyncio.Queue(maxsize=self._queue_max),
            tickers={t.upper() for t in (tickers or [])},
            types=(
                {t.lower() for t in types}
                if types
                else {"tick", "opportunity_version"}
            ),
        )
        async with self._lock:
            self._subscribers.append(sub)
        log.info(
            "pubsub.subscribed",
            tickers=sorted(sub.tickers) if sub.tickers else "*",
            active=len(self._subscribers),
        )
        return sub

    async def unsubscribe(self, sub: _Subscriber) -> None:
        async with self._lock:
            try:
                self._subscribers.remove(sub)
            except ValueError:
                return
        log.info("pubsub.unsubscribed", active=len(self._subscribers))

    async def update_subscription(
        self,
        sub: _Subscriber,
        *,
        tickers: list[str] | None = None,
        types: list[str] | None = None,
    ) -> None:
        async with self._lock:
            if tickers is not None:
                sub.tickers = {t.upper() for t in tickers}
            if types is not None:
                sub.types = {t.lower() for t in types}

    # -------------------------------------------------------------- internal
    async def _flush_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._tick_batch_s or 0.25)
            except asyncio.TimeoutError:
                pass
            await self._flush_once()

    async def _flush_once(self) -> None:
        async with self._lock:
            if not self._tick_buffer:
                return
            buffered = list(self._tick_buffer.values())
            self._tick_buffer.clear()
        for tick in buffered:
            payload = tick.to_payload()
            await self._dispatch(payload)
            self.published_ticks += 1

    async def _dispatch(self, payload: dict[str, Any]) -> None:
        msg_type = str(payload.get("type", ""))
        ticker = str(payload.get("ticker", "")).upper()
        async with self._lock:
            subscribers = list(self._subscribers)
        for sub in subscribers:
            if msg_type not in sub.types:
                continue
            if sub.tickers and ticker and ticker not in sub.tickers:
                continue
            try:
                sub.queue.put_nowait(payload)
            except asyncio.QueueFull:
                self.dropped_overflow += 1
                log.warning("pubsub.dropped", ticker=ticker, type=msg_type)
