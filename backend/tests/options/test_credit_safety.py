"""Boundary cases for the Credit Safety scoring function."""

from app.services.options.credit_safety import credit_safety_score


def test_ideal_setup_is_safe():
    out = credit_safety_score(
        prob_block=0.95,
        pin_risk=0.05,
        body_danger=0.1,
        event_risk=0.1,
        vol_regime="low",
    )
    assert out["label"] == "SAFE"
    assert out["score"] >= 7.0


def test_worst_setup_is_unsafe():
    out = credit_safety_score(
        prob_block=0.1,
        pin_risk=0.95,
        body_danger=0.95,
        event_risk=0.9,
        vol_regime="high",
    )
    assert out["label"] == "UNSAFE"
    assert out["score"] < 4.0


def test_medium_setup_is_caution():
    out = credit_safety_score(
        prob_block=0.55,
        pin_risk=0.45,
        body_danger=0.5,
        event_risk=0.5,
        vol_regime="medium",
    )
    assert out["label"] == "CAUTION"
    assert 4.0 <= out["score"] < 7.0


def test_components_are_inverted_correctly():
    out = credit_safety_score(
        prob_block=0.5,
        pin_risk=0.0,
        body_danger=0.0,
        event_risk=0.0,
        vol_regime="low",
    )
    # all "bad" inputs at zero → all component scores at 1.0
    comps = out["components"]
    assert comps["pin_risk"] == 1.0
    assert comps["body_danger"] == 1.0
    assert comps["event_risk"] == 1.0
