"""Threshold and fallback tests for ``extract_executive_summary``."""

from __future__ import annotations

from typing import Any

import pytest

from app.services.summary import extract_executive_summary
from app.services.summary.extractor import (
    _liquidity_from_volume,
    _move_prob_to_label,
    _confidence_from_calibration,
    _decision_from_credit_safety,
    _outlook_from_consensus,
    _iv_quality,
    _risk_from_blocks,
    _trim_sentence,
    _compose_summary,
    SUMMARY_MAX_CHARS,
)


def _base_options_block(**overrides: Any) -> dict[str, Any]:
    base = {
        "source": "realized_vol",
        "horizon_days": 3,
        "last_close": 100.0,
        "daily_vol_pct": 1.5,
        "expected_range": {"low": 96.0, "high": 104.0, "sigma_pct": 4.0, "confidence": 0.6},
        "move_probabilities": {
            "p_up_2pct": 0.18,
            "p_dn_2pct": 0.22,
            "p_up_3pct": 0.05,
            "p_dn_3pct": 0.06,
            "p_in_range_1sigma": 0.68,
        },
        "pin_risk": {"score": 0.2, "label": "Low", "nearest_round": 100.0, "distance_pct": 0.0},
        "body_danger": {
            "short_body_lo": 99.0,
            "short_body_hi": 101.0,
            "distance_pct": 0.5,
            "label": "Low",
        },
        "event_risk": {"score": 0.3, "label": "Low", "drivers": []},
        "credit_safety": {
            "score": 7.5,
            "label": "SAFE",
            "components": {
                "prob_block": 0.6,
                "pin_risk": 0.2,
                "body_danger": 0.3,
                "event_risk": 0.3,
                "vol_regime": 0.5,
            },
        },
        "reverse_bwb": {
            "score": 7.0,
            "label": "SAFE",
            "suggested_wing_width_pct": 2.5,
            "suggested_dte": 5,
            "rationale": "stable",
        },
    }
    base.update(overrides)
    return base


# --- Threshold-level helpers -------------------------------------------------


def test_decision_from_label_takes_precedence():
    assert _decision_from_credit_safety("SAFE", 4.0) == "SAFE"
    assert _decision_from_credit_safety("CAUTION", 9.5) == "WATCH"
    assert _decision_from_credit_safety("UNSAFE", 8.0) == "AVOID"


def test_decision_score_thresholds_when_label_missing():
    assert _decision_from_credit_safety(None, 7.0) == "SAFE"
    assert _decision_from_credit_safety(None, 6.99) == "WATCH"
    assert _decision_from_credit_safety(None, 4.0) == "WATCH"
    assert _decision_from_credit_safety(None, 3.99) == "AVOID"


def test_move_prob_thresholds():
    assert _move_prob_to_label(0.40) == "High"
    assert _move_prob_to_label(0.39) == "Medium"
    assert _move_prob_to_label(0.20) == "Medium"
    assert _move_prob_to_label(0.19) == "Low"
    assert _move_prob_to_label(None) == "Medium"


def test_confidence_uses_calibration_first():
    assert _confidence_from_calibration(0.65, None) == "High"
    assert _confidence_from_calibration(0.50, None) == "Medium"
    assert _confidence_from_calibration(0.20, None) == "Low"
    # Falls back to price_prediction.confidence when calibration absent.
    assert _confidence_from_calibration(None, 0.70) == "High"
    assert _confidence_from_calibration(None, None) == "Medium"


def test_outlook_volatile_overrides_stance_when_high_regime():
    assert _outlook_from_consensus("bullish", "high", None) == "Volatile"
    assert _outlook_from_consensus("neutral", "high", None) == "Volatile"


def test_outlook_maps_known_consensus_strings():
    assert _outlook_from_consensus("strong bullish", "low", None) == "Bullish"
    assert _outlook_from_consensus("weak bearish", "medium", None) == "Bearish"
    assert _outlook_from_consensus("mixed", "low", None) == "Mixed"
    assert _outlook_from_consensus("neutral", "low", None) == "Sideways"
    assert _outlook_from_consensus(None, "low", "bullish") == "Bullish"


def test_risk_takes_max_of_credit_safety_and_uncertainty():
    assert _risk_from_blocks("SAFE", "high") == "High"
    assert _risk_from_blocks("UNSAFE", "low") == "High"
    assert _risk_from_blocks("CAUTION", "low") == "Medium"
    assert _risk_from_blocks("SAFE", "low") == "Low"


def test_iv_quality_live_iv_floor_is_good():
    assert _iv_quality("high", 0.50, "live_iv") == "Good"
    assert _iv_quality("low", 0.80, "live_iv") == "Excellent"


def test_iv_quality_realized_vol_buckets():
    assert _iv_quality("high", 0.30, "realized_vol") == "Poor"
    assert _iv_quality("high", 0.80, "realized_vol") == "Good"
    assert _iv_quality("low", 0.80, "realized_vol") == "Excellent"
    assert _iv_quality("low", 0.20, "realized_vol") == "Fair"


def test_liquidity_buckets():
    assert _liquidity_from_volume(2.0) == "Excellent"
    assert _liquidity_from_volume(1.2) == "Good"
    assert _liquidity_from_volume(0.7) == "Fair"
    assert _liquidity_from_volume(0.4) == "Poor"
    assert _liquidity_from_volume(None) == "Fair"


def test_trim_sentence_respects_word_boundary():
    text = "This is a long sentence that should get truncated at a word boundary."
    out = _trim_sentence(text, 30)
    assert out.endswith("…")
    assert len(out) <= 31


def test_compose_summary_dedupes_and_caps_length():
    out = _compose_summary(
        consensus_summary="Outlook is balanced with mild downside.",
        dominant_narrative="Outlook is balanced with mild downside.",
        what_happened="Volume was light.",
        fallback_decision_line="Decision SAFE.",
    )
    # Duplicate first sentence is dropped; "Volume was light." remains.
    assert out.count("Outlook is balanced") == 1
    assert "Volume was light" in out
    assert len(out) <= SUMMARY_MAX_CHARS


def test_compose_summary_uses_fallback_when_all_inputs_blank():
    out = _compose_summary(None, None, "", "Decision SAFE.")
    assert out.startswith("Decision SAFE")


# --- Integration on full report dict ----------------------------------------


def test_extract_safe_report_v1_no_dil():
    report = {
        "options_intelligence": _base_options_block(),
        "_pipeline_meta": {
            "volatility_regime": "low",
            "price_snapshot": {"volume_vs_avg": 1.1},
        },
        "dominant_narrative": "Range-bound price action with no upcoming catalysts.",
    }
    summary = extract_executive_summary(report)
    assert summary.decision == "SAFE"
    assert summary.outlook in {"Sideways", "Mixed"}
    assert summary.credit_safety_score == 7.5
    assert summary.plus_move_risk == "Low"
    assert summary.minus_move_risk == "Medium"
    assert summary.expected_range.low == 96.0
    assert summary.expected_range.high == 104.0
    assert summary.event_risk == "Low"
    assert summary.iv_quality in {"Excellent", "Good"}
    assert summary.liquidity == "Good"
    assert summary.summary_version == 1
    assert "catalysts" in summary.summary.lower()


def test_extract_avoid_report_with_dil_v2():
    report = {
        "options_intelligence": _base_options_block(
            credit_safety={
                "score": 2.5,
                "label": "UNSAFE",
                "components": {
                    "prob_block": 0.4,
                    "pin_risk": 0.7,
                    "body_danger": 0.6,
                    "event_risk": 0.7,
                    "vol_regime": 0.8,
                },
            },
            move_probabilities={
                "p_up_2pct": 0.42,
                "p_dn_2pct": 0.45,
                "p_up_3pct": 0.18,
                "p_dn_3pct": 0.20,
                "p_in_range_1sigma": 0.32,
            },
            pin_risk={"score": 0.7, "label": "High", "nearest_round": 100.0, "distance_pct": 0.0},
            event_risk={"score": 0.8, "label": "High", "drivers": ["FOMC"]},
        ),
        "_pipeline_meta": {
            "volatility_regime": "high",
            "price_snapshot": {"volume_vs_avg": 1.8},
        },
        "deliberation_layer": {
            "consensus": {
                "consensus": "bearish",
                "uncertainty": "high",
                "debate_summary": "Models converge on a bearish 1-3d setup.",
                "calibration": {
                    "directional_conviction": 0.7,
                    "consensus_strength": 0.8,
                    "evidence_quality": 0.6,
                    "confidence_aggregate": 0.72,
                    "uncertainty": "high",
                },
            }
        },
        "dominant_narrative": "Macro selloff continues with sector breadth deteriorating.",
    }
    summary = extract_executive_summary(report)
    assert summary.decision == "AVOID"
    # high regime forces Volatile bucket regardless of stance
    assert summary.outlook == "Volatile"
    assert summary.risk == "High"
    assert summary.confidence == "High"  # confidence_aggregate >= 0.65
    assert summary.plus_move_risk == "High"
    assert summary.minus_move_risk == "High"
    assert summary.event_risk == "High"
    assert summary.pin_risk == "High"
    assert summary.liquidity == "Excellent"
    assert summary.summary_version == 2
    assert "Models converge" in summary.summary


def test_extract_returns_neutrals_on_empty_report():
    summary = extract_executive_summary({})
    assert summary.decision == "WATCH"
    assert summary.outlook == "Sideways"
    assert summary.risk == "Medium"
    assert summary.confidence == "Medium"
    assert summary.expected_range.low == 0.0
    assert summary.expected_range.high == 0.0
    assert summary.summary  # always non-empty fallback
    assert summary.summary_version == 1


@pytest.mark.parametrize(
    "vol_regime,expected_outlook",
    [
        ("low", "Sideways"),
        ("medium", "Sideways"),
        ("high", "Volatile"),
    ],
)
def test_outlook_regime_priority(vol_regime: str, expected_outlook: str):
    report = {
        "options_intelligence": _base_options_block(),
        "_pipeline_meta": {"volatility_regime": vol_regime},
        "deliberation_layer": {"consensus": {"consensus": "neutral"}},
    }
    summary = extract_executive_summary(report)
    assert summary.outlook == expected_outlook
