"""Tests for the analog forward-path simulator (Phase 7)."""

from __future__ import annotations

from app.services.analogs.setup_simulator import (
    _scale_strikes_to_analog,
    _simulate_one_analog,
)


def test_strikes_scale_proportionally():
    body, lo, hi = _scale_strikes_to_analog(
        analog_close=200.0,
        current_spot=400.0,
        current_body=400.0,
        current_wing_dollars=20.0,
    )
    # body sits at spot today → at the analog price too
    assert body == 200.0
    # wing dollars rebased to half the current size
    assert abs(lo - 190.0) < 0.01
    assert abs(hi - 210.0) < 0.01


def test_quiet_forward_path_retains_full_credit():
    out = _simulate_one_analog(
        analog_close=100.0,
        forward_path=[100.0, 100.2, 99.9, 100.1, 100.3],
        current_spot=100.0,
        current_body=110.0,
        current_wing_dollars=4.0,
        credit=1.0,
    )
    # body sits at 110 today (10% above), so when scaled body is at 110
    # forward path stays in 99..101 → never touched body or wings
    assert out["valid"]
    assert out["body_touched"] is False
    assert out["wing_touched"] is False
    assert out["credit_retained"] == 100.0


def test_terminal_inside_body_zone_zeros_credit():
    # Reverse-BWB max loss = price terminates INSIDE the body zone
    # (between wings). body=100, wings at ±5 → wing_lo=95, wing_hi=105.
    out = _simulate_one_analog(
        analog_close=100.0,
        forward_path=[100.0, 101.0, 100.5],  # parked in body zone
        current_spot=100.0,
        current_body=100.0,
        current_wing_dollars=5.0,
        credit=1.0,
    )
    assert out["valid"]
    assert out["wing_touched"] is True
    assert out["credit_retained"] == 0.0


def test_body_touch_without_terminal_in_body_partial_credit():
    # Path touches body intraday but terminal escapes outside the wing
    # zone (body=100, wings at 95/105). Terminal at 108 exits the body
    # zone → partial credit.
    out = _simulate_one_analog(
        analog_close=100.0,
        forward_path=[100.0, 100.1, 100.0, 108.0],
        current_spot=100.0,
        current_body=100.0,
        current_wing_dollars=5.0,
        credit=1.0,
    )
    assert out["valid"]
    assert out["body_touched"] is True
    assert out["wing_touched"] is False
    assert 0 < out["credit_retained"] < 100.0


def test_invalid_inputs_return_invalid_marker():
    out = _simulate_one_analog(
        analog_close=0.0,
        forward_path=[100.0],
        current_spot=100.0,
        current_body=100.0,
        current_wing_dollars=5.0,
        credit=1.0,
    )
    assert out["valid"] is False
