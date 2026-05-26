"""Sanity checks on the log-normal move-probability math."""

from app.services.options.probability import (
    move_probabilities,
    p_in_range,
    p_move_exceeds,
)


def test_symmetric_no_drift():
    p_up = p_move_exceeds(daily_vol_pct=2.0, horizon_days=3, move_pct=2.0)
    p_dn = p_move_exceeds(daily_vol_pct=2.0, horizon_days=3, move_pct=-2.0)
    assert abs(p_up - p_dn) < 0.01


def test_higher_vol_increases_tail_prob():
    low = p_move_exceeds(daily_vol_pct=1.0, horizon_days=3, move_pct=2.0)
    high = p_move_exceeds(daily_vol_pct=4.0, horizon_days=3, move_pct=2.0)
    assert high > low


def test_p_in_range_within_unit():
    p = p_in_range(daily_vol_pct=2.0, horizon_days=5, lo_pct=-5.0, hi_pct=5.0)
    assert 0.0 <= p <= 1.0
    # ±5% over 5 trading days at 2% daily vol covers ~1.1σ each side → >60% mass
    assert p > 0.6


def test_move_probabilities_dict_shape():
    out = move_probabilities(last_close=200.0, daily_vol_pct=2.0, horizon_days=3)
    for k in ("p_up_2pct", "p_dn_2pct", "p_up_3pct", "p_dn_3pct", "p_in_range_1sigma"):
        assert k in out
        assert 0.0 <= out[k] <= 1.0
    # 3% tail must be smaller than 2% tail
    assert out["p_up_3pct"] <= out["p_up_2pct"]
    assert out["p_dn_3pct"] <= out["p_dn_2pct"]


def test_zero_horizon_returns_zero():
    assert p_move_exceeds(daily_vol_pct=2.0, horizon_days=0, move_pct=1.0) == 0.0
    assert p_in_range(daily_vol_pct=2.0, horizon_days=0, lo_pct=-1.0, hi_pct=1.0) == 0.0
