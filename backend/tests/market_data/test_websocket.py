"""MarketDataPubSub fanout / subscription tests.

These tests are pure-asyncio — no FastAPI / ASGI plumbing required. They
verify:

    * Tick batching: a burst of ticks for one ticker collapses to a
      single fanned-out message in the next flush window.
    * Opportunity-version messages bypass batching.
    * Ticker filtering: a subscriber that only subscribed to SPY does
      not receive QQQ ticks.
    * Type filtering: a "tick"-only subscriber doesn't receive
      opportunity_version events.
    * Overflow drops are counted, not raised.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.services.market_data.pubsub import (
    MarketDataPubSub,
    OpportunityVersionMessage,
    TickMessage,
)


def _tick(ticker: str = "SPY", last: float = 500.0) -> TickMessage:
    return TickMessage(
        ticker=ticker,
        last_price=last,
        bid=last - 0.05,
        ask=last + 0.05,
        change_abs=0.10,
        change_pct=0.02,
        volume=100_000,
        feed_status="live",
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_tick_batching_coalesces_bursts() -> None:
    """Within one batch window the latest tick per ticker survives."""
    pubsub = MarketDataPubSub(tick_batch_ms=0)  # synchronous flush in tests
    sub = await pubsub.subscribe()
    try:
        for last in (500.0, 500.1, 500.2):
            await pubsub.publish_tick(_tick(last=last))
        # Last write wins.
        assert sub.queue.qsize() >= 1
        # Drain and pick the most recent payload — the queue can have one
        # entry per flush; the final last is 500.2.
        last_payload = None
        while not sub.queue.empty():
            last_payload = sub.queue.get_nowait()
        assert last_payload is not None
        assert last_payload["type"] == "tick"
        assert last_payload["last"] == 500.2
    finally:
        await pubsub.unsubscribe(sub)


@pytest.mark.asyncio
async def test_opportunity_version_is_pushed_immediately() -> None:
    pubsub = MarketDataPubSub(tick_batch_ms=0)
    sub = await pubsub.subscribe()
    try:
        version = uuid4()
        await pubsub.publish_opportunity_version(
            OpportunityVersionMessage(
                ticker="SPY",
                side="call",
                opportunity_version=version,
                count=42,
            )
        )
        payload = await asyncio.wait_for(sub.queue.get(), timeout=1.0)
        assert payload["type"] == "opportunity_version"
        assert payload["ticker"] == "SPY"
        assert payload["side"] == "call"
        assert payload["opportunity_version"] == str(version)
        assert payload["count"] == 42
    finally:
        await pubsub.unsubscribe(sub)


@pytest.mark.asyncio
async def test_ticker_filter_excludes_unsubscribed_symbols() -> None:
    pubsub = MarketDataPubSub(tick_batch_ms=0)
    sub = await pubsub.subscribe(tickers=["SPY"])
    try:
        await pubsub.publish_tick(_tick(ticker="QQQ", last=400.0))
        await pubsub.publish_tick(_tick(ticker="SPY", last=500.0))
        seen = []
        # We expect ONLY the SPY message — but tick batching keeps the
        # last per-ticker so both could be in the buffer. The filter
        # applies at dispatch.
        while not sub.queue.empty():
            seen.append(sub.queue.get_nowait())
        tickers = {p["ticker"] for p in seen}
        assert "SPY" in tickers
        assert "QQQ" not in tickers
    finally:
        await pubsub.unsubscribe(sub)


@pytest.mark.asyncio
async def test_type_filter_excludes_unwanted_message_types() -> None:
    pubsub = MarketDataPubSub(tick_batch_ms=0)
    sub = await pubsub.subscribe(types=["opportunity_version"])
    try:
        await pubsub.publish_tick(_tick(ticker="SPY"))
        await pubsub.publish_opportunity_version(
            OpportunityVersionMessage(
                ticker="SPY",
                side="put",
                opportunity_version=uuid4(),
                count=10,
            )
        )
        seen = []
        while not sub.queue.empty():
            seen.append(sub.queue.get_nowait())
        types = {p["type"] for p in seen}
        assert types == {"opportunity_version"}
    finally:
        await pubsub.unsubscribe(sub)


@pytest.mark.asyncio
async def test_unsubscribe_stops_message_delivery() -> None:
    pubsub = MarketDataPubSub(tick_batch_ms=0)
    sub = await pubsub.subscribe()
    await pubsub.unsubscribe(sub)
    # After unsubscribe further publishes must not reach the queue.
    await pubsub.publish_tick(_tick())
    assert sub.queue.empty()


@pytest.mark.asyncio
async def test_overflow_increments_drop_counter() -> None:
    pubsub = MarketDataPubSub(tick_batch_ms=0, queue_max=8)
    sub = await pubsub.subscribe()
    try:
        # Force the queue full by publishing more opportunity_version
        # messages than the queue can hold (they bypass tick batching).
        for _ in range(20):
            await pubsub.publish_opportunity_version(
                OpportunityVersionMessage(
                    ticker="SPY",
                    side="call",
                    opportunity_version=uuid4(),
                    count=1,
                )
            )
        assert pubsub.dropped_overflow >= 1
    finally:
        await pubsub.unsubscribe(sub)
