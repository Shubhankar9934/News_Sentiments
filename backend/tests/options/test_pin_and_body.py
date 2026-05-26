"""Pin-risk and body-danger boundary tests."""

from app.services.options.body_danger import body_danger_zone
from app.services.options.pin_risk import pin_risk


def test_pin_risk_near_round_number_is_high():
    out = pin_risk(last_close=200.10, daily_vol_pct=2.0, horizon_days=3)
    assert out["nearest_round"] == 200.0
    assert out["label"] in ("High", "Medium")


def test_pin_risk_far_from_round_number_is_low():
    # 202.5 sits at the midpoint between 200 and 205 (step=5). With low vol
    # the relative distance dominates and pin pressure disappears.
    out = pin_risk(last_close=202.5, daily_vol_pct=0.6, horizon_days=3)
    assert out["label"] == "Low"


def test_body_bounds_widen_with_vol():
    low_vol = body_danger_zone(last_close=200.0, daily_vol_pct=1.0, horizon_days=3)
    high_vol = body_danger_zone(last_close=200.0, daily_vol_pct=4.0, horizon_days=3)
    assert (high_vol["short_body_hi"] - high_vol["short_body_lo"]) > (
        low_vol["short_body_hi"] - low_vol["short_body_lo"]
    )


def test_body_label_is_high_when_spot_at_center():
    out = body_danger_zone(last_close=200.0, daily_vol_pct=2.0, horizon_days=3)
    # symmetric construction places spot at the center → highest danger
    assert out["label"] == "High"
