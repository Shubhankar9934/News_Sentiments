"""Tests for Phase 8 assessment-team intel expansion."""

from __future__ import annotations

from app.services.deliberation.intelligence.package_builder import (
    build_intelligence_package,
)
from app.services.deliberation.schemas import DeskResearchReport
from app.services.explainability.assessment_reasoning import (
    build_assessment_reasoning,
)


def test_intel_package_carries_new_blocks():
    desk = DeskResearchReport(
        role_key="options_desk",
        role_label="Options Desk",
        model="groq",
        analytical_view="neutral",
        confidence_in_analysis=0.6,
    )
    report = {
        "options_intelligence": {
            "credit_safety": {"score": 5.0, "label": "CAUTION"},
            "reverse_bwb": {"score": 5.0},
            "expected_range": {"low": 95, "high": 105},
            "pin_risk": {"score": 0.3, "label": "Medium"},
            "body_danger": {"label": "Medium"},
            "event_risk": {"score": 0.2, "label": "Low"},
            "move_probabilities": {"p_in_range_1sigma": 0.65},
            "structure_geometry": {"spot": 100.0, "body_strike": 100.0},
            "position_risk": {
                "probability_of_profit": 0.62,
                "probability_of_touch": 0.4,
                "probability_of_breakeven": 0.55,
                "probability_of_max_loss": 0.03,
                "expected_value_usd": 18.0,
            },
        },
        "_pipeline_meta": {
            "historical_analogs": [{"headline": "x", "close": 100.0}],
            "historical_analog_aggregates": {
                "n_setups": 12,
                "win_rate": 0.76,
                "avg_credit_retained": 83.0,
                "max_loss_frequency": 0.04,
            },
        },
        "explainability": {
            "macro_transmission": {
                "primary_shock": "iran_peace",
                "ticker_impact": "supportive",
                "chain": [],
            }
        },
    }
    pkg = build_intelligence_package(
        ticker="SPY",
        question="Should we enter this Reverse BWB?",
        trigger="reverse_bwb",
        desk_reports={"options_desk": desk},
        report=report,
    )
    assert "structure_geometry" in pkg.options_snapshot
    assert "position_risk" in pkg.options_snapshot
    assert "historical_analogs" in pkg.options_snapshot
    assert "macro_transmission" in pkg.options_snapshot


def test_assessment_reasoning_aggregates_from_round1():
    dil = {
        "assessment_layer": {
            "round1": {
                "openai_assessment_analyst": {
                    "assessment_label": "OpenAI Assessment Analyst",
                    "risk_lenses": {
                        "ticker_risk": "SPY is a broad-market ETF — single-name risk is low.",
                        "macro_transmission": "Iran peace deal is supportive for SPY via oil-down → inflation-down → yields-lower.",
                    },
                },
                "claude_risk_assessment_analyst": {
                    "assessment_label": "Claude Risk Assessment Analyst",
                    "risk_lenses": {
                        "structure_risk": "Body sits 0.4σ from spot with 60% body exposure — material tail.",
                        "position_risk": "PoT 40% combined with PoMaxLoss 3% leaves a tight margin.",
                    },
                },
            }
        }
    }
    out = build_assessment_reasoning(ticker="SPY", deliberation_layer=dil)
    assert out is not None
    lens_keys = {lens.lens for lens in out.lenses}
    assert "ticker_risk" in lens_keys
    assert "structure_risk" in lens_keys
    assert "macro_transmission" in lens_keys


def test_assessment_reasoning_returns_none_without_layer():
    assert (
        build_assessment_reasoning(ticker="SPY", deliberation_layer=None)
        is None
    )
