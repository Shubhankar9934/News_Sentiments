"""Shape-level tests for the dashboard route helpers."""

from __future__ import annotations

from app.services.dashboard.schemas import (
    DashboardTickerCard,
    WatchlistBatchStatus,
    empty_card,
)
from app.services.dashboard.watchlist import (
    ALL_WATCHLIST_TICKERS,
    WATCHLIST_TIERS,
    is_watchlist_ticker,
    tier_for,
)


def test_watchlist_count_and_order():
    assert len(ALL_WATCHLIST_TICKERS) == 12
    assert ALL_WATCHLIST_TICKERS[0] == "SPY"
    assert ALL_WATCHLIST_TICKERS[-1] == "META"


def test_tier_structure():
    assert len(WATCHLIST_TIERS) == 3
    for tier in WATCHLIST_TIERS:
        assert len(tier.tickers) == 4


def test_is_watchlist_ticker_case_insensitive():
    assert is_watchlist_ticker("spy")
    assert is_watchlist_ticker("META")
    assert not is_watchlist_ticker("XYZ")


def test_tier_for_returns_expected_keys():
    assert tier_for("SPY") == "tier-1"
    assert tier_for("AAPL") == "tier-2"
    assert tier_for("NVDA") == "tier-3"
    assert tier_for("ZZZ") is None


def test_empty_card_uses_pending_status():
    card = empty_card("SPY", "S&P 500", "tier-1")
    assert isinstance(card, DashboardTickerCard)
    assert card.status == "pending"
    assert card.reverse_bwb is None
    assert card.opportunities is None


def test_watchlist_batch_status_defaults_to_idle():
    status = WatchlistBatchStatus()
    assert status.state == "idle"
    assert status.current_ticker is None
    assert status.completed == []
    assert status.failed == []


def test_dashboard_ticker_report_response_accepts_snapshot():
    from datetime import UTC, datetime

    from app.services.dashboard.schemas import DashboardTickerReportResponse

    payload = DashboardTickerReportResponse(
        ticker="SPY",
        status="completed",
        research_report_id="00000000-0000-0000-0000-000000000001",
        generated_at=datetime.now(UTC),
        report_json={"deliberation_layer": {"status": "complete"}},
    )
    assert payload.ticker == "SPY"
    assert payload.report_json["deliberation_layer"]["status"] == "complete"
