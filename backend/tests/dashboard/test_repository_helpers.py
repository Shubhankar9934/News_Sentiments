"""Pure-Python helpers in the dashboard repository.

A full integration test of ``save_snapshot`` requires a live Postgres
test DB. These tests exercise the shape-level helpers (price snapshot
extraction, card building from ORM-like objects) so the read path stays
under coverage without a Postgres dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.db.repositories.dashboard_repository import (
    DashboardRepository,
    _extract_price_snapshot,
    _opportunity_model_to_schema,
    _summary_model_to_schema,
)


def test_extract_price_snapshot_returns_none_for_empty():
    assert _extract_price_snapshot(None) is None
    assert _extract_price_snapshot({}) is None
    assert _extract_price_snapshot({"_pipeline_meta": {}}) is None


def test_extract_price_snapshot_picks_up_pipeline_meta_fields():
    out = _extract_price_snapshot(
        {
            "_pipeline_meta": {
                "price_snapshot": {
                    "last_close": 123.45,
                    "daily_change_pct": -0.5,
                    "as_of": "2026-05-23T20:00:00Z",
                    "source": "polygon",
                }
            }
        }
    )
    assert out is not None
    assert out.price == 123.45
    assert out.daily_change_pct == -0.5
    assert out.source == "polygon"


def test_extract_price_snapshot_session_change_alias():
    """Some pipeline meta variants use session_change_pct instead."""

    out = _extract_price_snapshot(
        {"_pipeline_meta": {"price_snapshot": {"last_close": 50.0, "session_change_pct": 1.5}}}
    )
    assert out is not None and out.daily_change_pct == 1.5


def test_opportunity_model_to_schema_passthrough():
    row = SimpleNamespace(
        combo="100/102.5/105",
        expiry="2D",
        premium=90.0,
        margin=300.0,
        liquidity="Good",
        option_type="CALL",
        rank=0,
    )
    schema = _opportunity_model_to_schema(row)
    assert schema.combo == "100/102.5/105"
    assert schema.liquidity == "Good"


def test_opportunity_model_to_schema_upgrades_legacy_liquidity():
    row = SimpleNamespace(
        combo="100/102.5/105",
        expiry="2D",
        premium=90.0,
        margin=300.0,
        liquidity="Excellent",
        option_type="CALL",
        rank=0,
    )
    schema = _opportunity_model_to_schema(row)
    assert schema.liquidity == "Good"


def test_summary_model_to_schema_passthrough():
    row = SimpleNamespace(
        decision="WATCH",
        credit_safety_score=5.5,
        risk="Medium",
        confidence="Medium",
        today_outlook="Mixed",
        next_3d_outlook="Volatile",
        chance_up_2_3_pct="Medium",
        chance_down_2_3_pct="High",
        expected_range_today={"low": 100.0, "high": 105.0},
        expected_range_next_3d={"low": 95.0, "high": 110.0},
        danger_zone="+/-3% around current price",
        pin_risk="Medium",
        event_risk="High",
        iv_quality="Elevated",
        liquidity="Excellent",
        actual_dynamics_summary=["a", "b", "c"],
        updated_at=datetime.now(UTC),
    )
    schema = _summary_model_to_schema(row, "NVDA")
    assert schema.ticker == "NVDA"
    assert schema.credit_safety_score == 5.5
    assert schema.actual_dynamics_summary == ["a", "b", "c"]


def test_get_ticker_report_maps_orm_row():
    """Build response from an ORM-like row without Postgres."""

    report_row = SimpleNamespace(
        status="completed",
        research_report_id=None,
        generated_at=datetime.now(UTC),
        report_json={"ticker": "SPY", "deliberation_layer": {"status": "complete"}},
    )
    repo = DashboardRepository.__new__(DashboardRepository)

    async def _scalar(_stmt):
        return report_row

    repo._session = SimpleNamespace(scalar=_scalar)  # type: ignore[attr-defined]

    import asyncio

    out = asyncio.run(repo.get_ticker_report("SPY"))
    assert out is not None
    assert out.ticker == "SPY"
    assert out.status == "completed"
    assert out.report_json["deliberation_layer"]["status"] == "complete"


def test_get_ticker_report_returns_none_without_json():
    report_row = SimpleNamespace(
        status="completed",
        research_report_id=None,
        generated_at=datetime.now(UTC),
        report_json=None,
    )
    repo = DashboardRepository.__new__(DashboardRepository)

    async def _scalar(_stmt):
        return report_row

    repo._session = SimpleNamespace(scalar=_scalar)  # type: ignore[attr-defined]

    import asyncio

    out = asyncio.run(repo.get_ticker_report("SPY"))
    assert out is None
