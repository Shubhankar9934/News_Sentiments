"""Tests for the Liquidity Assessment explanation (Phase 3)."""

from __future__ import annotations

from app.services.explainability.liquidity_assessment import (
    build_liquidity_assessment,
)


def _options_intel(*, pin_score=0.85, pin_label="High", body_label="High", credit_label="SAFE"):
    return {
        "credit_safety": {"label": credit_label, "score": 6.5},
        "pin_risk": {"score": pin_score, "label": pin_label, "nearest_round": 600.0, "distance_pct": 0.4},
        "body_danger": {
            "short_body_lo": 595.0,
            "short_body_hi": 605.0,
            "distance_pct": 0.4,
            "label": body_label,
        },
    }


def test_spy_with_high_pin_shows_poor_execution_even_with_good_underlying():
    report = {"_pipeline_meta": {"price_snapshot": {"avg_volume_20d": 80_000_000}}}
    out = build_liquidity_assessment(
        ticker="SPY",
        report=report,
        options_intel=_options_intel(),
        deliberation_layer=None,
        summary=None,
    )
    assert out is not None
    assert out.underlying_liquidity.grade == "Good"
    assert out.options_liquidity.grade == "Good"
    assert out.execution_quality.grade == "Poor"
    assert "exit" in out.reason.lower() or "spread" in out.reason.lower()


def test_clean_setup_returns_all_good():
    report = {"_pipeline_meta": {"price_snapshot": {"avg_volume_20d": 80_000_000}}}
    out = build_liquidity_assessment(
        ticker="SPY",
        report=report,
        options_intel=_options_intel(
            pin_score=0.1, pin_label="Low", body_label="Low", credit_label="SAFE"
        ),
        deliberation_layer=None,
        summary=None,
    )
    assert out is not None
    assert out.underlying_liquidity.grade == "Good"
    assert out.options_liquidity.grade == "Good"
    assert out.execution_quality.grade == "Good"


def test_returns_none_without_options():
    out = build_liquidity_assessment(
        ticker="SPY",
        report={},
        options_intel=None,
        deliberation_layer=None,
        summary=None,
    )
    assert out is None


def test_thin_tape_underlying_drops_to_poor():
    report = {"_pipeline_meta": {"price_snapshot": {"avg_volume_20d": 50_000}}}
    out = build_liquidity_assessment(
        ticker="XYZ",
        report=report,
        options_intel=_options_intel(
            pin_score=0.1, pin_label="Low", body_label="Low", credit_label="SAFE"
        ),
        deliberation_layer=None,
        summary=None,
    )
    assert out is not None
    assert out.underlying_liquidity.grade == "Poor"
