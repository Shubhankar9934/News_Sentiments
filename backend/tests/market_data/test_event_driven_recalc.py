"""Event-driven recalc trigger tests.

The Workstation opportunity worker recalculates a ticker's opportunities
ONLY when a trigger fires:

    * ``startup``      first cycle after process start
    * ``market_open``  first cycle after the regular session opens
    * ``price_move``   underlying moved >= OPP_RECALC_PRICE_PCT
    * ``stale``        >= OPP_RECALC_MAX_AGE_S elapsed since last recalc
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.services.market_data.opportunity_worker import OpportunityEngineWorker


class _NoopPubSub:
    async def publish_tick(self, *a, **kw):
        pass

    async def publish_opportunity_version(self, *a, **kw):
        pass


class _NoopQuoteCache:
    def get_local(self, ticker):
        return None


def _settings(
    *,
    price_pct: float = 0.25,
    iv_pct: float = 3.0,
    max_age_s: int = 900,
) -> Settings:
    return Settings(
        IBKR_ENABLED=True,
        OPP_RECALC_PRICE_PCT=price_pct,
        OPP_RECALC_IV_PCT=iv_pct,
        OPP_RECALC_MAX_AGE_S=max_age_s,
    )


def _make_worker(**kwargs) -> OpportunityEngineWorker:
    return OpportunityEngineWorker(
        settings=_settings(**kwargs),
        opp_service=MagicMock(),  # type: ignore[arg-type]
        pubsub=_NoopPubSub(),  # type: ignore[arg-type]
        quote_cache=_NoopQuoteCache(),  # type: ignore[arg-type]
        watchlist=("SPY",),
    )


def test_first_cycle_triggers_startup() -> None:
    worker = _make_worker()
    assert worker._decide_recalc_trigger("SPY", last_price=750.0) == "startup"


def _seed_state(worker: OpportunityEngineWorker, *, price: float, at: datetime) -> None:
    """Pretend the ticker has already been recalced today during market hours."""
    state = worker._recalc_state["SPY"]
    state.last_recalc_at = at
    state.last_recalc_price = price
    state.last_market_open_date = datetime.now(UTC).date().isoformat()


def test_small_price_move_does_not_trigger() -> None:
    worker = _make_worker(price_pct=0.5)
    _seed_state(worker, price=750.0, at=datetime.now(UTC))
    # 0.1% move — below the 0.5% threshold.
    assert worker._decide_recalc_trigger("SPY", last_price=750.75) is None


def test_large_price_move_triggers() -> None:
    worker = _make_worker(price_pct=0.25)
    _seed_state(worker, price=750.0, at=datetime.now(UTC))
    # 0.5% move — over 0.25%.
    assert worker._decide_recalc_trigger("SPY", last_price=753.75) == "price_move"


def test_stale_elapsed_triggers() -> None:
    worker = _make_worker(max_age_s=600)
    _seed_state(
        worker,
        price=750.0,
        at=datetime.now(UTC) - timedelta(seconds=700),
    )
    assert worker._decide_recalc_trigger("SPY", last_price=750.0) == "stale"


def test_recently_recalced_with_no_movement_is_skipped() -> None:
    worker = _make_worker(max_age_s=900, price_pct=0.5)
    _seed_state(worker, price=750.0, at=datetime.now(UTC))
    assert worker._decide_recalc_trigger("SPY", last_price=750.0) is None
