"""Vol-regime sensitivity for Reverse-BWB suggestions."""

from app.services.options.reverse_bwb import reverse_bwb_suitability


def test_low_vol_tighter_wings_and_longer_dte():
    out = reverse_bwb_suitability(
        credit_safety_score=8.0,
        expected_range_sigma_pct=1.2,
        vol_regime="low",
        event_risk_score=0.1,
    )
    assert out["label"] == "SAFE"
    assert out["suggested_dte"] >= 10
    assert out["suggested_wing_width_pct"] <= 2.0


def test_high_vol_widens_wings_and_shortens_dte():
    out = reverse_bwb_suitability(
        credit_safety_score=5.0,
        expected_range_sigma_pct=5.5,
        vol_regime="high",
        event_risk_score=0.6,
    )
    assert out["suggested_wing_width_pct"] >= 2.5
    assert out["suggested_dte"] <= 5


def test_high_event_risk_shrinks_dte():
    base = reverse_bwb_suitability(
        credit_safety_score=6.0,
        expected_range_sigma_pct=2.0,
        vol_regime="medium",
        event_risk_score=0.1,
    )
    panic = reverse_bwb_suitability(
        credit_safety_score=6.0,
        expected_range_sigma_pct=2.0,
        vol_regime="medium",
        event_risk_score=0.85,
    )
    assert panic["suggested_dte"] < base["suggested_dte"]
