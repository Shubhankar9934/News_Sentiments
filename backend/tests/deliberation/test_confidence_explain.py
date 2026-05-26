"""Tests for the Confidence Calibration explanation (Phase 2)."""

from __future__ import annotations

from app.services.dashboard.schemas import ExpectedRange, ReverseBwbSummary
from app.services.deliberation.scoring.confidence_explain import (
    build_confidence_calibration,
)


def _make_summary(confidence: str = "Medium") -> ReverseBwbSummary:
    return ReverseBwbSummary(
        ticker="SPY",
        decision="Wait",
        credit_safety_score=4.0,
        risk="Medium",
        confidence=confidence,  # type: ignore[arg-type]
        today_outlook="Sideways",
        next_3d_outlook="Sideways",
        chance_up_2_3_pct="Medium",
        chance_down_2_3_pct="Medium",
        expected_range_today=ExpectedRange(low=100.0, high=110.0),
        expected_range_next_3d=ExpectedRange(low=95.0, high=115.0),
        danger_zone="None",
        pin_risk="Medium",
        event_risk="Medium",
        iv_quality="Average",
        liquidity="Average",
        actual_dynamics_summary=["a", "b", "c"],
    )


def _make_layer(council_conf: float | None = 0.7) -> dict:
    layer = {
        "consensus": {
            "calibration": {
                "confidence_aggregate": 0.84,
                "consensus_strength": 0.62,
                "evidence_quality": 0.55,
            }
        },
        "metrics": {"contradiction_density": 0.36},
    }
    if council_conf is not None:
        layer["council_layer"] = {
            "consensus": {"confidence": council_conf},
            "round1": {"a": {}, "b": {}, "c": {}, "d": {}, "e": {}},
        }
    return layer


def test_calibration_pulls_signals_from_existing_layer():
    layer = _make_layer()
    summary = _make_summary("Medium")
    out = build_confidence_calibration(
        ticker="SPY", deliberation_layer=layer, summary=summary
    )
    assert out is not None
    assert out.raw_desk_confidence.value == 84.0
    assert out.cross_agent_agreement.value == 62.0
    assert out.evidence_overlap.value == 55.0
    assert out.contradiction_penalty.value is not None
    assert out.contradiction_penalty.value < 0
    assert out.council_confidence is not None
    assert out.final_confidence_bucket == "Medium"


def test_bucket_mirrors_card_when_summary_present():
    layer = _make_layer(council_conf=0.95)
    summary = _make_summary("Low")
    out = build_confidence_calibration(
        ticker="SPY", deliberation_layer=layer, summary=summary
    )
    assert out is not None
    assert out.final_confidence_bucket == "Low"


def test_returns_none_without_layer():
    assert (
        build_confidence_calibration(
            ticker="SPY", deliberation_layer=None, summary=None
        )
        is None
    )


def test_council_row_optional_when_council_missing():
    layer = _make_layer(council_conf=None)
    out = build_confidence_calibration(
        ticker="SPY", deliberation_layer=layer, summary=None
    )
    assert out is not None
    assert out.council_confidence is None
