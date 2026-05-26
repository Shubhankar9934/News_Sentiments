"""Tests for the Credit Safety Score decomposition (Phase 1)."""

from __future__ import annotations

from app.services.explainability.credit_safety_breakdown import (
    build_credit_safety_breakdown,
)


def _make_options_intel(score: float, *, pin: float = 0.2, event: float = 0.2) -> dict:
    return {
        "credit_safety": {"score": score, "label": "CAUTION"},
        "expected_range": {"low": 100.0, "high": 110.0, "sigma_pct": 2.0, "confidence": 0.6},
        "pin_risk": {"score": pin, "label": "Medium", "nearest_round": 600.0, "distance_pct": 0.3},
        "event_risk": {"score": event, "label": "Medium", "drivers": ["FOMC"]},
        "body_danger": {
            "short_body_lo": 95.0,
            "short_body_hi": 105.0,
            "distance_pct": 1.2,
            "label": "Medium",
        },
    }


def test_breakdown_sums_to_final_score():
    options_intel = _make_options_intel(4.0)
    report = {"_pipeline_meta": {"volatility_regime": "medium"}}
    bd = build_credit_safety_breakdown(
        ticker="SPY", report=report, options_intel=options_intel, summary=None
    )
    assert bd is not None

    total = bd.move_stability.value + sum(
        row.delta or 0.0
        for row in [
            bd.pin_risk_impact,
            bd.event_risk_impact,
            bd.volatility_impact,
            bd.structure_placement_impact,
            bd.liquidity_impact,
        ]
    )
    assert abs(total - bd.final_credit_safety) < 0.05


def test_breakdown_final_score_matches_card():
    options_intel = _make_options_intel(7.5)
    report = {"_pipeline_meta": {"volatility_regime": "low"}}
    bd = build_credit_safety_breakdown(
        ticker="SPY", report=report, options_intel=options_intel, summary=None
    )
    assert bd is not None
    assert bd.final_credit_safety == 7.5


def test_high_pin_creates_negative_delta():
    options_intel = _make_options_intel(3.0, pin=0.85)
    report = {"_pipeline_meta": {"volatility_regime": "high"}}
    bd = build_credit_safety_breakdown(
        ticker="SPY", report=report, options_intel=options_intel, summary=None
    )
    assert bd is not None
    assert bd.pin_risk_impact.delta is not None
    assert bd.pin_risk_impact.delta < 0


def test_builder_returns_none_without_options():
    out = build_credit_safety_breakdown(
        ticker="SPY", report={}, options_intel=None, summary=None
    )
    assert out is None


def test_builder_returns_none_without_score():
    options_intel = {"credit_safety": {}}
    out = build_credit_safety_breakdown(
        ticker="SPY", report={}, options_intel=options_intel, summary=None
    )
    assert out is None
