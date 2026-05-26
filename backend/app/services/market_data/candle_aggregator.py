"""In-memory 1-minute OHLCV candle aggregator.

Accumulates live ticks from ``MarketDataWorker._price_loop`` into
1-minute candle slots.  Every 60 seconds ``_candle_flush_loop`` calls
``drain_closed(now)`` which returns all completed candles and removes
them from the in-memory state.  Open (current-minute) candles are never
returned until the minute boundary has passed so partials are never
persisted.

Intended for a single-writer, single-reader pattern (worker only).
No locking — all calls happen on the same asyncio event loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class _CandleSlot:
    ticker: str
    minute_ts: datetime  # UTC floored to the minute boundary
    open: float
    high: float
    low: float
    close: float
    volume: int  # latest cumulative day-volume from IBKR


@dataclass
class Candle1m:
    """Completed 1-minute OHLCV candle ready for DB persistence."""

    ticker: str
    ts: datetime  # UTC minute boundary
    open: float
    high: float
    low: float
    close: float
    volume: int


class CandleAggregator:
    """Stateful per-ticker 1-minute OHLCV accumulator."""

    def __init__(self) -> None:
        self._slots: dict[str, _CandleSlot] = {}

    def on_tick(
        self,
        ticker: str,
        price: float,
        volume: int | None,
        ts: datetime,
    ) -> None:
        """Update the open candle slot for ``ticker``.

        IBKR volume is a cumulative day counter, so we always store the
        latest value rather than summing; the per-minute delta can be
        derived later if needed.
        """
        minute_ts = ts.replace(second=0, microsecond=0, tzinfo=UTC)
        upper = ticker.upper()
        slot = self._slots.get(upper)

        if slot is None or slot.minute_ts != minute_ts:
            # New minute (or first tick) — open a fresh slot.
            self._slots[upper] = _CandleSlot(
                ticker=upper,
                minute_ts=minute_ts,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume or 0,
            )
        else:
            slot.high = max(slot.high, price)
            slot.low = min(slot.low, price)
            slot.close = price
            if volume is not None:
                slot.volume = volume

    def drain_closed(self, now: datetime) -> list[Candle1m]:
        """Return all candles whose minute boundary has passed.

        Removes them from in-memory state so they are not returned again.
        The current (open) candle is never returned.
        """
        current_minute = now.replace(second=0, microsecond=0, tzinfo=UTC)
        closed: list[Candle1m] = []
        done: list[str] = []

        for ticker, slot in self._slots.items():
            if slot.minute_ts < current_minute:
                closed.append(
                    Candle1m(
                        ticker=ticker,
                        ts=slot.minute_ts,
                        open=slot.open,
                        high=slot.high,
                        low=slot.low,
                        close=slot.close,
                        volume=slot.volume,
                    )
                )
                done.append(ticker)

        for t in done:
            del self._slots[t]

        return closed

    @property
    def open_candle_count(self) -> int:
        return len(self._slots)
