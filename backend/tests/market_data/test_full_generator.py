"""Full-enumeration combo geometry tests.

The Reverse BWB Trading Workstation generator stores every valid
(long_wing_a, short_body, long_wing_b) triplet. These tests lock down
the enumerator: count, distinctness, strike-side respect, wing-width
bounds, and asymmetric coverage.
"""

from __future__ import annotations

import pytest

from app.services.market_data.combo_geometry import (
    ReverseBwbCandidate,
    enumerate_candidates,
    numeric_liquidity,
)


def test_enumerate_call_keeps_strikes_at_or_above_spot() -> None:
    strikes = [240.0, 245.0, 250.0, 255.0, 260.0, 265.0, 270.0]
    last_close = 250.0
    candidates = enumerate_candidates(
        side="CALL",
        strikes=strikes,
        last_close=last_close,
        wing_min_strikes=1,
        wing_max_strikes=3,
    )
    assert candidates  # non-empty
    for c in candidates:
        assert c.long_wing_a >= last_close
        assert c.short_body >= last_close
        assert c.long_wing_b >= last_close
        assert len({c.long_wing_a, c.short_body, c.long_wing_b}) == 3


def test_enumerate_put_keeps_strikes_at_or_below_spot() -> None:
    strikes = [220.0, 225.0, 230.0, 235.0, 240.0, 245.0, 250.0]
    last_close = 240.0
    candidates = enumerate_candidates(
        side="PUT",
        strikes=strikes,
        last_close=last_close,
        wing_min_strikes=1,
        wing_max_strikes=3,
    )
    assert candidates
    for c in candidates:
        assert c.long_wing_a <= last_close
        assert c.short_body <= last_close
        assert c.long_wing_b <= last_close


def test_enumerate_produces_many_candidates() -> None:
    """A ~25-strike chain across the configured wing window should yield
    well over 100 candidates per side — large enough that legacy top-N
    caps cannot satisfy 'generate everything'."""
    strikes = [float(700 + i) for i in range(40)]  # 700..739
    last_close = 720.0
    candidates = enumerate_candidates(
        side="CALL",
        strikes=strikes,
        last_close=last_close,
        wing_min_strikes=1,
        wing_max_strikes=10,
    )
    assert len(candidates) >= 100


def test_enumerate_handles_asymmetric_wings() -> None:
    strikes = [240.0, 245.0, 250.0, 255.0, 260.0, 265.0, 270.0]
    candidates = enumerate_candidates(
        side="CALL",
        strikes=strikes,
        last_close=240.0,
        wing_min_strikes=1,
        wing_max_strikes=4,
    )
    # At least one candidate must have left != right (the eponymous
    # broken wing).
    found_broken = False
    for c in candidates:
        if c.wing_left != c.wing_right:
            found_broken = True
            break
    assert found_broken


def test_enumerate_empty_when_no_same_side_strikes() -> None:
    """A spot above the highest strike leaves no CALL-side body
    candidate — the enumerator must return [] cleanly."""
    strikes = [100.0, 105.0]
    assert enumerate_candidates(
        side="CALL",
        strikes=strikes,
        last_close=200.0,
        wing_min_strikes=1,
        wing_max_strikes=3,
    ) == []


def test_enumerate_deduplicates_symmetric_pairs() -> None:
    """Symmetric wings are visited twice in the (left, right) double loop;
    the result must contain each triplet only once."""
    strikes = [240.0, 245.0, 250.0, 255.0, 260.0]
    candidates = enumerate_candidates(
        side="CALL",
        strikes=strikes,
        last_close=240.0,
        wing_min_strikes=1,
        wing_max_strikes=2,
    )
    keys = [(c.long_wing_a, c.short_body, c.long_wing_b) for c in candidates]
    assert len(keys) == len(set(keys))


def test_numeric_liquidity_min_over_legs() -> None:
    assert numeric_liquidity(oi_leg1=100, oi_leg2=200, oi_leg3=50) == 50
    assert numeric_liquidity(oi_leg1=None, oi_leg2=200, oi_leg3=50) == 0
    assert numeric_liquidity(oi_leg1=0, oi_leg2=200, oi_leg3=50) == 0


def test_from_strikes_records_wing_distances() -> None:
    cand = ReverseBwbCandidate.from_strikes(
        side="CALL",
        long_wing_a=750.0,
        short_body=755.0,
        long_wing_b=765.0,
    )
    assert pytest.approx(cand.wing_left) == 5.0
    assert pytest.approx(cand.wing_right) == 10.0
    assert cand.max_risk == 10.0
    assert cand.combo_label() == "750/755/765"
