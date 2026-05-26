"""Pure-compute tests for the Reverse BWB Workstation opportunity engine.

The engine itself is exercised end-to-end in ``test_full_generator.py``
with a mocked IBKR client. The cases here lock down the side-effect-free
helpers: premium math, expiry labels, and credit efficiency.
"""

from __future__ import annotations

from app.services.market_data.market_data_service import OptionQuote
from app.services.market_data.options_opportunity_service import (
    OptionsOpportunityService,
    _credit_efficiency,
    _expiry_label,
)


def _quote(bid: float, ask: float) -> OptionQuote:
    return OptionQuote(
        con_id=42,
        bid=bid,
        ask=ask,
        last=(bid + ask) / 2,
        open_interest=500,
        volume=100,
        implied_vol=0.18,
    )


def test_compute_premium_4leg_credit_case() -> None:
    """Classic credit BWB: 2 * body > both wings, so the net is negative."""
    long_wing_a = _quote(bid=0.95, ask=1.05)  # mid ~1.00
    short_body = _quote(bid=4.90, ask=5.10)   # mid ~5.00
    long_wing_b = _quote(bid=1.45, ask=1.55)  # mid ~1.50
    # Net = 1.00 + 1.50 - 2 * 5.00 = -7.50  => $750 credit per contract.
    premium = OptionsOpportunityService._compute_premium(
        long_wing_a, short_body, long_wing_b
    )
    assert premium is not None
    assert abs(premium - (-7.5)) < 1e-6


def test_compute_premium_returns_none_when_legs_missing() -> None:
    leg_a = OptionQuote(con_id=1, bid=None, ask=None, last=None, open_interest=10, volume=10)
    leg_b = _quote(bid=2.0, ask=2.5)
    leg_c = _quote(bid=1.0, ask=1.5)
    assert OptionsOpportunityService._compute_premium(leg_a, leg_b, leg_c) is None


def test_compute_premium_preserves_sign_for_debit_case() -> None:
    """Debit case (positive premium) — generator keeps the row but the
    UI will color it red and credit_efficiency falls to 0."""
    long_wing_a = _quote(bid=4.95, ask=5.05)
    short_body = _quote(bid=1.95, ask=2.05)
    long_wing_b = _quote(bid=4.95, ask=5.05)
    premium = OptionsOpportunityService._compute_premium(
        long_wing_a, short_body, long_wing_b
    )
    assert premium is not None
    # Net = 5.00 + 5.00 - 2 * 2.00 = +6.00 (debit)
    assert premium > 0


def test_credit_efficiency_zero_for_debit() -> None:
    # Positive per-share premium = debit; no credit to measure.
    assert _credit_efficiency(0.6, 600.0) == 0.0


def test_credit_efficiency_for_credit_row() -> None:
    # 0.60 credit per share = $60 per contract; $525 margin => 11.43%.
    assert abs(_credit_efficiency(-0.60, 525.0) - 11.4286) < 1e-3


def test_credit_efficiency_safe_when_margin_zero() -> None:
    assert _credit_efficiency(-0.50, 0.0) == 0.0


def test_expiry_label_progression() -> None:
    assert _expiry_label(0) == "0D"
    assert _expiry_label(1) == "1D"
    assert _expiry_label(8) == "8D"
