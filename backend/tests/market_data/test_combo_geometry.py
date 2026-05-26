"""Reverse-BWB strike-construction tests.

Confirms the shared ``combo_geometry`` module produces the expected
candidate set for representative tickers across the watchlist:

    - SPY around $750 with $5 strike step
    - AAPL around $230 with $1 strike step
    - NVDA around $130 with $1 strike step
"""

from __future__ import annotations

import pytest

from app.services.market_data.combo_geometry import (
    ReverseBwbCandidate,
    build_candidates,
    derive_dte_pair,
    grade_liquidity,
    round_strike,
    strike_step,
)


def test_strike_step_buckets() -> None:
    assert strike_step(750.0) == 5.0
    assert strike_step(230.0) == 1.0
    assert strike_step(130.0) == 1.0
    assert strike_step(50.0) == 0.5
    assert strike_step(10.0) == 0.5


def test_round_strike_snaps_to_step() -> None:
    assert round_strike(752.4, 5.0) == 750.0
    assert round_strike(752.6, 5.0) == 755.0
    assert round_strike(229.6, 1.0) == 230.0
    assert round_strike(0.0, 0.5) == 0.0


def test_call_candidates_use_higher_strikes_for_spy() -> None:
    candidates = build_candidates(
        side="CALL",
        last_close=750.0,
        sigma_dollars=10.0,
        step=5.0,
        offsets_sigma=(0.5, 1.0),
    )
    assert len(candidates) == 2
    for c in candidates:
        # The new 4-leg BWB places the short body on the CALL side of spot;
        # the two wings sandwich it. Legacy aliases (short_inner ==
        # long_wing_a, long_short == short_body, long_outer == long_wing_b)
        # still resolve.
        assert c.short_body > 750.0
        # Asymmetric wings are allowed but build_candidates returns
        # symmetric pairs.
        assert pytest.approx(c.wing_left) == c.wing_right
        # All three strikes are distinct.
        assert len({c.long_wing_a, c.short_body, c.long_wing_b}) == 3


def test_put_candidates_use_lower_strikes_for_spy() -> None:
    candidates = build_candidates(
        side="PUT",
        last_close=750.0,
        sigma_dollars=10.0,
        step=5.0,
    )
    assert len(candidates) == 2
    for c in candidates:
        assert c.short_body < 750.0
        assert len({c.long_wing_a, c.short_body, c.long_wing_b}) == 3


def test_candidates_are_distinct_strikes() -> None:
    """Wing widths must be at least one strike step so the three legs are distinct."""
    for last_close, sigma, step in [
        (750.0, 10.0, 5.0),
        (230.0, 4.0, 1.0),
        (130.0, 3.0, 1.0),
    ]:
        candidates = build_candidates(
            side="CALL",
            last_close=last_close,
            sigma_dollars=sigma,
            step=step,
        )
        assert candidates
        for c in candidates:
            assert len({c.long_wing_a, c.short_body, c.long_wing_b}) == 3


def test_zero_or_negative_inputs_yield_empty() -> None:
    assert build_candidates(side="CALL", last_close=0.0, sigma_dollars=10.0, step=5.0) == []
    assert build_candidates(side="CALL", last_close=750.0, sigma_dollars=0.0, step=5.0) == []
    assert (
        build_candidates(side="CALL", last_close=-100.0, sigma_dollars=10.0, step=5.0)
        == []
    )


def test_combo_label_uses_three_strike_format() -> None:
    candidate = ReverseBwbCandidate.from_strikes(
        side="CALL",
        long_wing_a=750.0,
        short_body=755.0,
        long_wing_b=765.0,
        offset_sigma=0.5,
    )
    assert candidate.combo_label() == "750/755/765"
    # 4-leg BWB max risk = wider wing.
    assert candidate.max_risk == 10.0


def test_combo_label_renders_decimal_strikes() -> None:
    candidate = ReverseBwbCandidate.from_strikes(
        side="PUT",
        long_wing_a=22.5,
        short_body=22.0,
        long_wing_b=21.0,
        offset_sigma=0.5,
    )
    assert candidate.combo_label() == "22.5/22/21"


def test_derive_dte_pair_default_progression() -> None:
    short, long = derive_dte_pair(2)
    assert short == 2
    assert long >= short + 3
    short, long = derive_dte_pair(7)
    assert long >= short + 3
    short, long = derive_dte_pair(None)
    assert short >= 1


# --------------------------------------------------------------------------
# Liquidity grading
# --------------------------------------------------------------------------
def test_liquidity_excellent_for_top_tier_metrics() -> None:
    assert grade_liquidity(oi_min=1500, vol_min=300, spread_pct=0.5) == "Excellent"


def test_liquidity_good_for_solid_metrics() -> None:
    assert grade_liquidity(oi_min=400, vol_min=80, spread_pct=2.0) == "Good"


def test_liquidity_average_for_modest_metrics() -> None:
    assert grade_liquidity(oi_min=120, vol_min=20, spread_pct=4.0) == "Average"


def test_liquidity_poor_when_spread_blows_out() -> None:
    assert grade_liquidity(oi_min=120, vol_min=20, spread_pct=8.0) == "Poor"


def test_liquidity_unknown_inputs_default_to_average() -> None:
    assert grade_liquidity(oi_min=None, vol_min=None, spread_pct=None) == "Average"
