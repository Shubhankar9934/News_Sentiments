"""Tests for closed-form position-risk math (Phase 5)."""

from __future__ import annotations

from app.services.options.position_risk import compute_position_risk


def test_deep_otm_body_has_low_pot():
    out = compute_position_risk(
        spot=100.0,
        body_strike=140.0,
        wing_width_pct=2.0,
        credit=1.0,
        sigma_pct=2.0,
        dte=7,
    )
    assert out is not None
    assert out["probability_of_touch"] < 0.2


def test_atm_body_high_pot():
    out = compute_position_risk(
        spot=100.0,
        body_strike=100.0,
        wing_width_pct=2.0,
        credit=1.0,
        sigma_pct=4.0,
        dte=7,
    )
    assert out is not None
    assert out["probability_of_touch"] > 0.4


def test_probabilities_within_bounds():
    out = compute_position_risk(
        spot=100.0,
        body_strike=100.0,
        wing_width_pct=2.0,
        credit=1.0,
        sigma_pct=3.0,
        dte=5,
    )
    assert out is not None
    for key in (
        "probability_of_profit",
        "probability_of_touch",
        "probability_of_breakeven",
        "probability_of_max_loss",
    ):
        assert 0.0 <= out[key] <= 1.0


def test_invalid_inputs_return_none():
    assert (
        compute_position_risk(
            spot=0.0,
            body_strike=100.0,
            wing_width_pct=2.0,
            credit=1.0,
            sigma_pct=2.0,
            dte=7,
        )
        is None
    )
    assert (
        compute_position_risk(
            spot=100.0,
            body_strike=100.0,
            wing_width_pct=2.0,
            credit=1.0,
            sigma_pct=2.0,
            dte=0,
        )
        is None
    )


def test_expected_value_is_finite_number():
    out = compute_position_risk(
        spot=100.0,
        body_strike=100.0,
        wing_width_pct=2.0,
        credit=1.0,
        sigma_pct=2.0,
        dte=7,
    )
    assert out is not None
    ev = out["expected_value_usd"]
    assert isinstance(ev, (int, float))
    # EV must lie inside the [-(max_loss*100), credit*100] band.
    max_loss = (100.0 * 0.02 - 1.0) * 100.0
    credit_cap = 1.0 * 100.0
    assert -max_loss - 1 <= ev <= credit_cap + 1
