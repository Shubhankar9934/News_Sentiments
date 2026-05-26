"""Worker behavior when IBKR is offline / errors during a refresh.

Verifies that:
    - Price loop short-circuits cleanly when the connection is not connected.
    - A per-ticker exception in the opportunity cycle does not abort other tickers.
    - Skipped generate() results do not trigger any DB writes.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.services.market_data.options_opportunity_service import OpportunityResult


class _FakeConnection:
    def __init__(self, *, connected: bool = False) -> None:
        self._connected = connected

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def ib(self):
        return object() if self._connected else None


class _FakeMarketData:
    def __init__(self) -> None:
        self.subscribed: list[str] = []
        self.cancelled = False

    async def subscribe_quotes(self, symbols):
        self.subscribed.extend(s.upper() for s in symbols)
        return True

    async def drain_quotes(self):
        return []

    async def cancel_subscriptions(self):
        self.cancelled = True

    # Expose _subs so _mark_stale_if_needed doesn't crash
    class _Subs:
        slots: dict = {}

    _subs = _Subs()


class _FakeQuoteCache:
    def get_local(self, ticker):
        return None

    async def set(self, quote):
        pass

    def get_all(self):
        return {}


class _FakePubSub:
    async def start(self):
        pass

    async def stop(self):
        pass

    async def publish_tick(self, *a, **kw):
        pass

    async def publish_opportunity_version(self, *a, **kw):
        pass


def _settings() -> Settings:
    return Settings(
        IBKR_ENABLED=True,
        MARKET_DATA_PRICE_FLUSH_MS=10,
        MARKET_DATA_OPP_INTERVAL_S=5,
        MARKET_DATA_STALE_THRESHOLD_S=10,
    )


@pytest.mark.asyncio
async def test_disconnected_worker_does_not_subscribe_quotes() -> None:
    from app.services.market_data.worker import MarketDataWorker

    md = _FakeMarketData()
    worker = MarketDataWorker(
        settings=_settings(),
        connection=_FakeConnection(connected=False),
        market_data=md,  # type: ignore[arg-type]
        watchlist=("SPY", "QQQ"),
        pubsub=_FakePubSub(),  # type: ignore[arg-type]
        quote_cache=_FakeQuoteCache(),  # type: ignore[arg-type]
    )
    await worker.start()
    await asyncio.sleep(0.05)
    assert md.subscribed == [], "should not subscribe when disconnected"
    await worker.stop()
    assert md.cancelled is True


@pytest.mark.asyncio
async def test_opportunity_cycle_isolates_per_ticker_errors() -> None:
    """One bad ticker must not abort the rest of the cycle."""
    from app.services.market_data.opportunity_worker import OpportunityEngineWorker

    worker = OpportunityEngineWorker(
        settings=_settings(),
        opp_service=MagicMock(),  # type: ignore[arg-type]
        pubsub=_FakePubSub(),  # type: ignore[arg-type]
        quote_cache=_FakeQuoteCache(),  # type: ignore[arg-type]
        watchlist=("SPY", "QQQ", "AAPL"),
    )

    visits: list[str] = []

    async def fake_maybe_recalc(ticker: str) -> bool:
        visits.append(ticker)
        if ticker == "QQQ":
            raise RuntimeError("simulated chain failure")
        return False

    worker._maybe_recalc_one_ticker = fake_maybe_recalc  # type: ignore[assignment]
    await worker._opportunity_cycle()
    assert visits == ["SPY", "QQQ", "AAPL"]


@pytest.mark.asyncio
async def test_skipped_results_do_not_persist() -> None:
    """If ``generate()`` returns a skipped reason, no DB writes happen."""
    from app.services.market_data.opportunity_worker import OpportunityEngineWorker

    opp_service = MagicMock()

    async def fake_generate(ticker: str, last_price=None):
        return OpportunityResult(ticker=ticker, skipped_reason="not_connected")

    opp_service.generate = fake_generate

    worker = OpportunityEngineWorker(
        settings=_settings(),
        opp_service=opp_service,  # type: ignore[arg-type]
        pubsub=_FakePubSub(),  # type: ignore[arg-type]
        quote_cache=_FakeQuoteCache(),  # type: ignore[arg-type]
        watchlist=("SPY",),
    )

    import app.services.market_data.opportunity_worker as opp_mod
    from contextlib import asynccontextmanager

    class _StubRepo:
        async def get_quote(self, *args, **kwargs):
            return None

        async def replace_opportunities(self, *args, **kwargs):
            raise AssertionError("must not write when skipped")

        async def append_history(self, *args, **kwargs):
            raise AssertionError("must not write when skipped")

        async def commit(self):
            raise AssertionError("must not commit when skipped")

    @asynccontextmanager
    async def _fake_session_ctx():
        yield _StubRepo()

    class _FakeSessionLocal:
        def __call__(self):
            return _fake_session_ctx()

    original = opp_mod.SessionLocal
    original_repo = opp_mod.MarketDataRepository
    opp_mod.SessionLocal = _FakeSessionLocal()  # type: ignore[assignment]
    opp_mod.MarketDataRepository = lambda session: session  # type: ignore[assignment]
    try:
        did_recalc = await worker._maybe_recalc_one_ticker("SPY")
        assert did_recalc is False
    finally:
        opp_mod.SessionLocal = original  # type: ignore[assignment]
        opp_mod.MarketDataRepository = original_repo  # type: ignore[assignment]
