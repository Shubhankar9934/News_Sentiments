"""Shared fixtures for dashboard service tests."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def sample_report() -> dict[str, Any]:
    """A trimmed but realistic report dict — enough surface for summarizer,
    opportunity generator and repository tests to consume without touching
    the live pipeline.
    """

    return {
        "ticker": "NVDA",
        "data_mode": "real",
        "data_quality_note": "All sources online",
        "articles_analyzed": 14,
        "overall_sentiment_score": 0.18,
        "overall_sentiment_label": "Mixed",
        "dominant_narrative": "Datacenter demand vs. China export controls.",
        "what_happened": "Q1 beat; guidance held; new China rules in focus.",
        "price_movers": "Export-control headline drove afternoon weakness.",
        "key_events": [
            {
                "type": "Earnings",
                "description": "Q1 EPS beat by 12%",
                "impact": "High",
                "impact_score": 0.82,
            },
            {
                "type": "Regulatory",
                "description": "US tightens China AI-chip export rules",
                "impact": "High",
                "impact_score": 0.74,
            },
        ],
        "price_prediction": {
            "last_close": 220.0,
            "low": 215.0,
            "base": 222.0,
            "high": 228.0,
            "bias": "Mixed",
            "volatility_regime": "high",
        },
        "executive_summary": {
            "decision": "WATCH",
            "credit_safety_score": 5.3,
            "outlook": "Mixed",
            "risk": "Medium",
            "confidence": "Medium",
            "summary": "Watch list — vol regime is high.",
            "summary_version": 1,
        },
        "options_intelligence": {
            "source": "realized_vol",
            "horizon_days": 3,
            "last_close": 220.0,
            "daily_vol_pct": 2.1,
            "expected_range": {
                "low": 213.5,
                "high": 226.5,
                "sigma_pct": 2.95,
                "confidence": 0.62,
            },
            "move_probabilities": {
                "p_up_2pct": 0.31,
                "p_dn_2pct": 0.29,
                "p_up_3pct": 0.18,
                "p_dn_3pct": 0.17,
                "p_in_range_1sigma": 0.66,
            },
            "pin_risk": {
                "score": 0.55,
                "label": "Medium",
                "nearest_round": 220.0,
                "distance_pct": 0.0,
            },
            "body_danger": {
                "short_body_lo": 217.0,
                "short_body_hi": 223.0,
                "distance_pct": 1.36,
                "label": "Medium",
            },
            "event_risk": {
                "score": 0.81,
                "label": "High",
                "drivers": ["Earnings", "Regulatory"],
            },
            "credit_safety": {
                "score": 5.3,
                "label": "CAUTION",
                "components": {
                    "prob_block": 0.66,
                    "pin_risk": 0.55,
                    "body_danger": 0.5,
                    "event_risk": 0.81,
                    "vol_regime": 0.7,
                },
            },
            "reverse_bwb": {
                "score": 5.1,
                "label": "CAUTION",
                "suggested_wing_width_pct": 2.5,
                "suggested_dte": 5,
                "rationale": "elevated event risk; trim wings",
            },
        },
        "_pipeline_meta": {
            "report_id": "00000000-0000-0000-0000-000000000001",
            "volatility_regime": "high",
            "price_snapshot": {
                "last_close": 220.0,
                "daily_change_pct": -0.85,
                "as_of": "2026-05-23T20:00:00Z",
                "source": "polygon",
            },
        },
    }


@pytest.fixture
def sample_summary_payload() -> dict[str, Any]:
    return {
        "ticker": "NVDA",
        "decision": "WATCH",
        "credit_safety_score": 5.3,
        "risk": "High",
        "confidence": "Medium",
        "today_outlook": "Volatile",
        "next_3d_outlook": "Mixed",
        "chance_up_2_3_pct": "Medium",
        "chance_down_2_3_pct": "Medium",
        "expected_range_today": {"low": 213.5, "high": 226.5},
        "expected_range_next_3d": {"low": 208.7, "high": 231.3},
        "danger_zone": "+/-1.4% around current price",
        "pin_risk": "Medium",
        "event_risk": "High",
        "iv_quality": "Elevated",
        "liquidity": "Excellent",
        "actual_dynamics_summary": [
            "Q1 print beat but the China export rule is dominating tape.",
            "Implied vol is sitting in elevated territory ahead of catalysts.",
            "Range expansion likely; credit collectors should narrow wings.",
        ],
    }
