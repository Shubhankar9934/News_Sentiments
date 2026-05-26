"""Tests for Reverse-BWB structure geometry (Phase 4a)."""

from __future__ import annotations

from app.services.options.structure_geometry import compute_structure_geometry


def test_basic_geometry_round_trip():
    geo = compute_structure_geometry(
        spot=600.0,
        body_strike=600.0,
        wing_width_pct=2.0,
        credit=5.0,
        dte=7,
        daily_vol_pct=1.0,
    )
    assert geo is not None
    assert geo.spot == 600.0
    assert geo.body_strike == 600.0
    assert geo.wing_width_dollars == 12.0
    assert geo.max_loss == 7.0
    assert geo.upper_breakeven == 605.0
    assert geo.lower_breakeven == 595.0
    # Body distance is 0 because body sits at spot
    assert geo.distance_to_body_pct == 0.0
    assert geo.body_exposure_pct > 0


def test_geometry_off_spot_body_exposure_lower():
    near = compute_structure_geometry(
        spot=600.0,
        body_strike=600.0,
        wing_width_pct=2.0,
        credit=5.0,
        dte=7,
        daily_vol_pct=1.0,
    )
    far = compute_structure_geometry(
        spot=600.0,
        body_strike=640.0,
        wing_width_pct=2.0,
        credit=5.0,
        dte=7,
        daily_vol_pct=1.0,
    )
    assert near is not None and far is not None
    assert far.body_exposure_pct < near.body_exposure_pct


def test_geometry_invalid_inputs_return_none():
    assert (
        compute_structure_geometry(
            spot=0.0,
            body_strike=600.0,
            wing_width_pct=2.0,
            credit=5.0,
            dte=7,
            daily_vol_pct=1.0,
        )
        is None
    )
    assert (
        compute_structure_geometry(
            spot=600.0,
            body_strike=600.0,
            wing_width_pct=2.0,
            credit=5.0,
            dte=0,
            daily_vol_pct=1.0,
        )
        is None
    )


def test_credit_efficiency_and_risk_reward_sane():
    geo = compute_structure_geometry(
        spot=100.0,
        body_strike=100.0,
        wing_width_pct=5.0,
        credit=1.0,
        dte=14,
        daily_vol_pct=1.0,
    )
    assert geo is not None
    # wing_dollars = 5; credit_efficiency = 1/5 = 0.2
    assert abs(geo.credit_efficiency - 0.2) < 1e-3
    # max_loss = 5 - 1 = 4; risk_reward = 1/4 = 0.25
    assert abs(geo.risk_reward - 0.25) < 1e-3
