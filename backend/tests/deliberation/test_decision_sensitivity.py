"""Unit tests for Phase 11 decision-sensitivity builders."""

from __future__ import annotations

from typing import Any

from app.services.dashboard.schemas import (
    DecisionSensitivityExplain,
    ExpectedRange,
    ReverseBwbSummary,
)
from app.services.explainability.decision_sensitivity import (
    build_analyst_disagreement,
    build_assumptions,
    build_decision_sensitivity,
    build_key_drivers,
    build_triggers,
)


def _summary(**overrides: Any) -> ReverseBwbSummary:
    base: dict[str, Any] = dict(
        ticker="SPY",
        decision="Wait",
        credit_safety_score=5.0,
        risk="Medium",
        confidence="Medium",
        today_outlook="Sideways",
        next_3d_outlook="Sideways",
        chance_up_2_3_pct="Medium",
        chance_down_2_3_pct="Medium",
        expected_range_today=ExpectedRange(low=445.0, high=455.0),
        expected_range_next_3d=ExpectedRange(low=440.0, high=460.0),
        danger_zone="Body sits at 450 spot.",
        pin_risk="Medium",
        event_risk="Medium",
        iv_quality="Average",
        liquidity="Good",
        actual_dynamics_summary=["a", "b", "c"],
    )
    base.update(overrides)
    return ReverseBwbSummary(**base)


def _options_intel(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ticker": "SPY",
        "last_close": 450.0,
        "expected_range": {"low": 445.0, "high": 455.0, "sigma_pct": 1.5, "confidence": 0.6},
        "horizon_days": 3,
        "credit_safety": {
            "score": 5.0,
            "label": "CAUTION",
            "components": {
                "prob_block": 4.0,
                "pin_risk": 1.0,
                "body_danger": 1.5,
                "event_risk": 0.8,
                "vol_regime": 0.3,
            },
        },
        "body_danger": {
            "short_body_lo": 449.0,
            "short_body_hi": 451.0,
            "distance_pct": 0.2,
            "label": "High",
        },
        "pin_risk": {
            "label": "Medium",
            "score": 0.5,
            "nearest_round": 450.0,
            "distance_pct": 0.0,
        },
        "event_risk": {
            "label": "Medium",
            "score": 0.5,
            "drivers": ["FOMC Wednesday", "CPI Thursday"],
        },
        "iv_intel": {"iv30": 15.0, "rv20": 12.0, "vol_regime": "normal"},
        "structure_geometry": {
            "spot": 450.0,
            "body_strike": 450.0,
            "wing_width_pct": 1.5,
            "wing_width_dollars": 6.75,
            "credit": 0.5,
            "max_loss": 6.25,
            "dte": 3,
            "distance_to_body_pct": 0.0,
            "distance_to_body_sigma": 0.0,
            "body_exposure_pct": 50.0,
            "wing_protection_ratio": 12.5,
            "credit_efficiency": 0.074,
            "risk_reward": 0.08,
            "upper_breakeven": 456.75,
            "lower_breakeven": 443.25,
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Key drivers
# ---------------------------------------------------------------------------


def test_key_drivers_sum_to_100_pct():
    summary = _summary()
    rows = build_key_drivers(summary=summary, options_intel=_options_intel())
    assert rows
    total = sum(r.weight_pct for r in rows)
    assert abs(total - 100.0) <= 0.5


def test_key_drivers_high_pin_dominates_for_avoid():
    summary = _summary(decision="Avoid", pin_risk="High")
    intel = _options_intel(
        credit_safety={
            "score": 2.5,
            "label": "UNSAFE",
            "components": {
                "prob_block": 4.0,
                "pin_risk": 2.5,  # huge pin deduction
                "body_danger": 0.3,
                "event_risk": 0.4,
                "vol_regime": 0.2,
            },
        }
    )
    rows = build_key_drivers(summary=summary, options_intel=intel)
    assert rows[0].label == "Pin Risk"
    assert rows[0].direction == "supports"
    assert rows[0].weight_pct > 40.0


def test_key_drivers_clean_state_neutral_row():
    summary = _summary(decision="Enter", liquidity="Good")
    intel = _options_intel(
        credit_safety={
            "score": 8.5,
            "label": "SAFE",
            "components": {
                "prob_block": 4.0,
                "pin_risk": 0.0,
                "body_danger": 0.0,
                "event_risk": 0.0,
                "vol_regime": 0.0,
            },
        }
    )
    rows = build_key_drivers(summary=summary, options_intel=intel)
    assert len(rows) == 1
    assert rows[0].direction == "neutral"
    assert rows[0].weight_pct == 100.0


# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------


def test_assumptions_include_iv_and_macro_baseline():
    summary = _summary()
    out = build_assumptions(
        summary=summary,
        options_intel=_options_intel(),
        deliberation_layer=None,
        report={"options_intelligence": _options_intel()},
    )
    labels = [a.label for a in out]
    assert any("IV" in label for label in labels)
    assert any("macro" in label.lower() for label in labels)


def test_assumptions_flag_event_when_earnings_in_drivers():
    summary = _summary()
    intel = _options_intel(
        event_risk={
            "label": "High",
            "score": 0.8,
            "drivers": ["Earnings Thursday after close"],
        }
    )
    out = build_assumptions(
        summary=summary,
        options_intel=intel,
        deliberation_layer=None,
        report={"options_intelligence": intel},
    )
    assert any("event" in a.label.lower() or "earnings" in (a.basis or "").lower()
               for a in out)
    # Earnings flagged ⇒ at least one assumption marked high-fragility.
    assert any(a.fragility == "high" for a in out)


def test_assumptions_high_fragility_when_macro_shock_present():
    summary = _summary()
    intel = _options_intel()
    report = {
        "options_intelligence": intel,
        "explainability": {
            "macro_transmission": {
                "primary_shock": "iran_peace",
                "chain": [],
            }
        },
    }
    out = build_assumptions(
        summary=summary,
        options_intel=intel,
        deliberation_layer={"foo": "bar"},
        report=report,
    )
    macro_row = next(a for a in out if "macro" in a.label.lower())
    assert macro_row.fragility == "high"


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------


def test_triggers_wait_decision_lists_enter_and_avoid_branches():
    summary = _summary()
    triggers = build_triggers(summary=summary, options_intel=_options_intel())
    targets = {t.target_decision for t in triggers}
    assert targets == {"Enter", "Avoid"}
    for t in triggers:
        assert t.conditions


def test_triggers_avoid_decision_offers_enter_and_wait():
    summary = _summary(decision="Avoid", pin_risk="High", event_risk="High",
                       credit_safety_score=2.0)
    triggers = build_triggers(summary=summary, options_intel=_options_intel())
    targets = {t.target_decision for t in triggers}
    assert "Enter" in targets
    assert "Wait" in targets


def test_triggers_enter_decision_offers_wait_and_avoid():
    summary = _summary(decision="Enter", pin_risk="Low", event_risk="Low",
                       credit_safety_score=8.0, liquidity="Good")
    triggers = build_triggers(summary=summary, options_intel=_options_intel())
    targets = {t.target_decision for t in triggers}
    assert "Wait" in targets
    assert "Avoid" in targets


def test_triggers_enter_branch_mentions_spot_breakeven_when_body_zone():
    summary = _summary()
    triggers = build_triggers(summary=summary, options_intel=_options_intel())
    enter = next(t for t in triggers if t.target_decision == "Enter")
    assert any("breakeven" in c.lower() or "spot" in c.lower() for c in enter.conditions)


# ---------------------------------------------------------------------------
# Analyst disagreement
# ---------------------------------------------------------------------------


def _opinion(role: str, today: str, nxt: str, chance_up: str, chance_dn: str,
             risk: str = "Medium") -> dict[str, Any]:
    return {
        "model": f"model-{role}",
        "assessment_role": role,
        "assessment_label": role.title().replace("_", " "),
        "credit_safety_score": 5.0,
        "risk": risk,
        "confidence": "Medium",
        "today_outlook": today,
        "next_3d_outlook": nxt,
        "chance_up_2_3_pct": chance_up,
        "chance_down_2_3_pct": chance_dn,
        "expected_range_today": {"low": 445.0, "high": 455.0},
        "expected_range_next_3d": {"low": 440.0, "high": 460.0},
        "danger_zone": "Body holds.",
        "pin_risk": "Medium",
        "event_risk": "Medium",
        "iv_quality": "Average",
        "liquidity": "Good",
        "actual_dynamics_summary": ["a", "b", "c"],
        "reasoning_steps": [{"title": f"{role} headline", "analysis": "..."}],
    }


def test_disagreement_returns_none_when_no_deliberation():
    assert build_analyst_disagreement(deliberation_layer=None) is None
    assert build_analyst_disagreement(deliberation_layer={}) is None


def test_disagreement_splits_three_distinct_stances():
    deliberation = {
        "assessment_layer": {
            "round1": {
                "openai_analyst": _opinion(
                    "openai_analyst", "Bullish", "Bullish", "High", "Low"
                ),
                "claude_analyst": _opinion(
                    "claude_analyst", "Sideways", "Sideways", "Medium", "Medium"
                ),
                "deepseek_analyst": _opinion(
                    "deepseek_analyst", "Bearish", "Bearish", "Low", "High"
                ),
            },
            "round2": {
                "openai_analyst": {
                    "enum_disagreements": ["event_risk: I say Low, others say Medium"],
                    "numeric_disagreements": ["credit_safety: I say 7, others say 5"],
                },
            },
        }
    }
    out = build_analyst_disagreement(deliberation_layer=deliberation)
    assert out is not None
    assert out.converged is False
    stances = {row.stance for row in out.stances}
    assert stances == {"Bullish", "Bearish", "Neutral"}
    assert out.main_conflict is not None
    assert out.stance_counts == {"Bullish": 1, "Neutral": 1, "Bearish": 1}


def test_disagreement_converged_when_all_agree():
    deliberation = {
        "assessment_layer": {
            "round1": {
                "openai_analyst": _opinion(
                    "openai_analyst", "Bullish", "Bullish", "High", "Low"
                ),
                "claude_analyst": _opinion(
                    "claude_analyst", "Bullish", "Bullish", "High", "Low"
                ),
            },
            "round2": {},
        }
    }
    out = build_analyst_disagreement(deliberation_layer=deliberation)
    assert out is not None
    assert out.converged is True
    assert out.main_conflict is None


def test_disagreement_prefers_revised_opinion_when_round3_present():
    deliberation = {
        "assessment_layer": {
            "round1": {
                "openai_analyst": _opinion(
                    "openai_analyst", "Bullish", "Bullish", "High", "Low"
                ),
            },
            "round3": {
                "openai_analyst": {
                    "revised_opinion": _opinion(
                        "openai_analyst", "Bearish", "Bearish", "Low", "High"
                    )
                }
            },
        }
    }
    out = build_analyst_disagreement(deliberation_layer=deliberation)
    assert out is not None
    assert out.stances[0].stance == "Bearish"


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


def test_build_decision_sensitivity_full_payload():
    summary = _summary()
    report = {"ticker": "SPY", "options_intelligence": _options_intel()}
    deliberation = {
        "assessment_layer": {
            "round1": {
                "openai_analyst": _opinion(
                    "openai_analyst", "Bullish", "Bullish", "High", "Low"
                ),
            },
            "round2": {},
        }
    }
    out = build_decision_sensitivity(
        ticker="SPY",
        report=report,
        deliberation_layer=deliberation,
        summary=summary,
    )
    assert isinstance(out, DecisionSensitivityExplain)
    assert out.current_decision == "Wait"
    assert out.key_drivers
    assert out.assumptions
    assert out.triggers
    assert out.analyst_disagreement is not None


def test_build_decision_sensitivity_missing_summary_returns_none():
    assert (
        build_decision_sensitivity(
            ticker="SPY",
            report={"options_intelligence": _options_intel()},
            deliberation_layer=None,
            summary=None,
        )
        is None
    )


def test_build_decision_sensitivity_missing_options_intel_returns_none():
    assert (
        build_decision_sensitivity(
            ticker="SPY",
            report={},
            deliberation_layer=None,
            summary=_summary(),
        )
        is None
    )
