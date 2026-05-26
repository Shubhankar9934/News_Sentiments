"""History archive payload tests.

The append-only ``ticker_option_opportunity_history`` table preserves every
recalc cycle for backtesting / replay. These tests confirm:

    * Each row maps the LiveOpportunity into a row payload that includes
      the ``opportunity_version`` and ``snapshot_date``.
    * ``replace_opportunities`` / ``append_history`` operate on different
      tables — confirming the worker can write both in the same session.
    * ``append_history`` accepts an empty list as a no-op.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.services.market_data.repository import (
    MarketDataRepository,
    _history_row_payload,
    _live_opp_row_payload,
)
from app.services.market_data.schemas import LiveOpportunity


def _opp(*, ticker: str = "SPY", side: str = "call", premium: float = -0.6) -> LiveOpportunity:
    return LiveOpportunity(
        ticker=ticker,
        side=side,  # type: ignore[arg-type]
        rank=0,
        combo="740/735/725",
        strike_long_wing_a=740.0,
        strike_short_body=735.0,
        strike_long_wing_b=725.0,
        expiration="20260530",
        expiry_days=5,
        delta_pct=1.42,
        premium=premium,
        init_margin=525.0,
        maint_margin=420.0,
        liquidity=2354,
        minimum_open_interest=2354,
        minimum_volume=120,
        oi_leg1=2400,
        oi_leg2=2354,
        oi_leg3=2500,
        vol_leg1=120,
        vol_leg2=150,
        vol_leg3=130,
        iv_leg1=0.32,
        iv_leg2=0.31,
        iv_leg3=0.30,
        mid_leg1=1.80,
        mid_leg2=3.80,
        mid_leg3=5.20,
        credit_efficiency=11.43,
        ranking_score=0.78,
        underlying_price=738.5,
        iv=0.31,
        opportunity_version=uuid4(),
        generated_at=datetime.now(UTC),
    )


def test_history_payload_includes_version_and_snapshot_date() -> None:
    opp = _opp()
    row = _history_row_payload(opp, fallback_updated_at=datetime.now(UTC))

    assert row["opportunity_version"] == opp.opportunity_version
    assert row["snapshot_date"] == opp.generated_at.date()
    assert row["ticker"] == "SPY"
    assert row["side"] == "call"
    assert row["combo"] == "740/735/725"
    # Per-leg payload preserved.
    assert row["oi_leg1"] == 2400 and row["oi_leg3"] == 2500
    assert row["vol_leg2"] == 150
    # Score / efficiency / strike triplet preserved.
    assert float(row["credit_efficiency"]) == pytest.approx(11.43)
    assert float(row["ranking_score"]) == pytest.approx(0.78)
    assert float(row["strike_long_wing_a"]) == pytest.approx(740.0)


def test_history_payload_falls_back_to_now_when_generated_missing() -> None:
    opp = _opp()
    opp.generated_at = None  # type: ignore[assignment]
    fallback = datetime(2026, 5, 25, 18, 30, tzinfo=UTC)
    row = _history_row_payload(opp, fallback_updated_at=fallback)
    assert row["generated_at"] == fallback
    assert row["snapshot_date"] == fallback.date()


def test_live_and_history_payloads_diverge_on_legacy_columns() -> None:
    """The live table keeps legacy ``oi_min``/``vol_min``/``spread_pct`` for
    back-compat; the history table doesn't have them."""
    opp = _opp()
    now = datetime.now(UTC)
    live = _live_opp_row_payload(opp, fallback_updated_at=now)
    hist = _history_row_payload(opp, fallback_updated_at=now)

    assert "oi_min" in live and "vol_min" in live and "spread_pct" in live
    assert "oi_min" not in hist
    assert "vol_min" not in hist
    assert "spread_pct" not in hist
    assert "snapshot_date" in hist
    assert "snapshot_date" not in live


class _SessionSpy:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[object, object]] = []

    async def execute(self, stmt, params=None):  # noqa: D401
        self.execute_calls.append((stmt, params))

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_append_history_no_op_for_empty_list() -> None:
    spy = _SessionSpy()
    repo = MarketDataRepository(spy)  # type: ignore[arg-type]
    await repo.append_history([])
    assert spy.execute_calls == []


@pytest.mark.asyncio
async def test_append_history_inserts_one_row_per_opportunity() -> None:
    spy = _SessionSpy()
    repo = MarketDataRepository(spy)  # type: ignore[arg-type]
    rows = [_opp(side="call"), _opp(side="call"), _opp(side="put")]
    await repo.append_history(rows)
    assert len(spy.execute_calls) == 1
    _, params = spy.execute_calls[0]
    assert isinstance(params, list)
    assert len(params) == 3
    assert {r["side"] for r in params} == {"call", "put"}
