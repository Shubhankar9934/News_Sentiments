"""Unit tests for the deterministic Assessment-Team consensus merge.

Covers:
* Numeric median for ``credit_safety_score`` + expected ranges.
* Modal vote with conservative tie-breaking for enum fields.
* ``danger_zone`` picked from the highest-risk member.
* ``actual_dynamics_summary`` is deduped + capped at 4 sentences.
* ``fallback_consensus_from`` promotes a single opinion to a consensus.
"""

from __future__ import annotations

import pytest

from app.services.assessment.round4_consensus import (
    fallback_consensus_from,
    synthesize_assessment_consensus,
)
from app.services.assessment.schemas import (
    AssessmentMemberOpinion,
    AssessmentRevision,
)
from app.services.dashboard.schemas import ExpectedRange


def _opinion(
    *,
    role: str,
    model: str = "gpt",
    score: float,
    risk: str = "Medium",
    confidence: str = "Medium",
    today: str = "Sideways",
    next3d: str = "Sideways",
    chance_up: str = "Medium",
    chance_down: str = "Medium",
    today_range: tuple[float, float] = (100.0, 110.0),
    next_range: tuple[float, float] = (95.0, 115.0),
    danger_zone: str = "body 100-102",
    pin_risk: str = "Medium",
    event_risk: str = "Medium",
    iv_quality: str = "Average",
    liquidity: str = "Average",
    dynamics: list[str] | None = None,
    error: str | None = None,
) -> AssessmentMemberOpinion:
    return AssessmentMemberOpinion(
        model=model,  # type: ignore[arg-type]
        assessment_role=role,  # type: ignore[arg-type]
        assessment_label=role.replace("_", " ").title(),
        credit_safety_score=score,
        risk=risk,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        today_outlook=today,  # type: ignore[arg-type]
        next_3d_outlook=next3d,  # type: ignore[arg-type]
        chance_up_2_3_pct=chance_up,  # type: ignore[arg-type]
        chance_down_2_3_pct=chance_down,  # type: ignore[arg-type]
        expected_range_today=ExpectedRange(low=today_range[0], high=today_range[1]),
        expected_range_next_3d=ExpectedRange(low=next_range[0], high=next_range[1]),
        danger_zone=danger_zone,
        pin_risk=pin_risk,  # type: ignore[arg-type]
        event_risk=event_risk,  # type: ignore[arg-type]
        iv_quality=iv_quality,  # type: ignore[arg-type]
        liquidity=liquidity,  # type: ignore[arg-type]
        actual_dynamics_summary=dynamics
        or [
            "Move is bounded by the body for now.",
            "Pin pressure within tolerances at the body.",
            "Macro tape is quiet enough for the structure.",
        ],
        error=error,
    )


def test_median_numeric_modal_enums() -> None:
    op_a = _opinion(role="openai_assessment_analyst", score=8.0)
    op_b = _opinion(
        role="claude_risk_assessment_analyst", score=7.0, risk="High"
    )
    op_c = _opinion(role="deepseek_quant_assessment_analyst", score=6.0)

    consensus, meta = synthesize_assessment_consensus(
        {
            "openai_assessment_analyst": op_a,
            "claude_risk_assessment_analyst": op_b,
            "deepseek_quant_assessment_analyst": op_c,
        },
        {},
    )

    assert consensus is not None
    assert consensus.credit_safety_score == 7.0
    assert consensus.risk == "Medium"
    assert meta["members_valid"] == 3


def test_tie_break_picks_conservative_risk() -> None:
    op_a = _opinion(role="openai_assessment_analyst", score=6.0, risk="Low")
    op_b = _opinion(
        role="claude_risk_assessment_analyst", score=6.0, risk="High"
    )

    consensus, _ = synthesize_assessment_consensus(
        {
            "openai_assessment_analyst": op_a,
            "claude_risk_assessment_analyst": op_b,
        },
        {},
    )
    assert consensus is not None
    # Tie between Low + High; conservative tie-break keeps the riskier label.
    assert consensus.risk == "High"


def test_tie_break_picks_conservative_confidence() -> None:
    op_a = _opinion(role="openai_assessment_analyst", score=6.0, confidence="High")
    op_b = _opinion(
        role="claude_risk_assessment_analyst", score=6.0, confidence="Low"
    )

    consensus, _ = synthesize_assessment_consensus(
        {
            "openai_assessment_analyst": op_a,
            "claude_risk_assessment_analyst": op_b,
        },
        {},
    )
    assert consensus is not None
    assert consensus.confidence == "Low"


def test_tie_break_picks_conservative_iv_quality() -> None:
    op_a = _opinion(role="openai_assessment_analyst", score=6.0, iv_quality="Good")
    op_b = _opinion(
        role="claude_risk_assessment_analyst", score=6.0, iv_quality="Poor"
    )

    consensus, _ = synthesize_assessment_consensus(
        {
            "openai_assessment_analyst": op_a,
            "claude_risk_assessment_analyst": op_b,
        },
        {},
    )
    assert consensus is not None
    assert consensus.iv_quality == "Poor"


def test_expected_range_is_median_and_normalised() -> None:
    op_a = _opinion(
        role="openai_assessment_analyst",
        score=6.0,
        today_range=(95.0, 105.0),
        next_range=(90.0, 110.0),
    )
    op_b = _opinion(
        role="claude_risk_assessment_analyst",
        score=6.0,
        today_range=(100.0, 110.0),
        next_range=(95.0, 115.0),
    )
    op_c = _opinion(
        role="deepseek_quant_assessment_analyst",
        score=6.0,
        today_range=(105.0, 115.0),
        next_range=(100.0, 120.0),
    )

    consensus, _ = synthesize_assessment_consensus(
        {
            "openai_assessment_analyst": op_a,
            "claude_risk_assessment_analyst": op_b,
            "deepseek_quant_assessment_analyst": op_c,
        },
        {},
    )
    assert consensus is not None
    assert consensus.expected_range_today.low == 100.0
    assert consensus.expected_range_today.high == 110.0
    assert consensus.expected_range_next_3d.low == 95.0
    assert consensus.expected_range_next_3d.high == 115.0


def test_danger_zone_taken_from_highest_pin_risk_member() -> None:
    op_a = _opinion(
        role="openai_assessment_analyst",
        score=6.0,
        pin_risk="Low",
        danger_zone="body 100-102 (calm)",
    )
    op_b = _opinion(
        role="claude_risk_assessment_analyst",
        score=6.0,
        pin_risk="High",
        danger_zone="body 100-102 (heavy pin risk)",
    )

    consensus, _ = synthesize_assessment_consensus(
        {
            "openai_assessment_analyst": op_a,
            "claude_risk_assessment_analyst": op_b,
        },
        {},
    )
    assert consensus is not None
    assert "heavy pin risk" in consensus.danger_zone


def test_dynamics_dedup_and_cap() -> None:
    shared = "Move is bounded by the body for now."
    op_a = _opinion(
        role="openai_assessment_analyst",
        score=6.0,
        dynamics=[shared, "Pin pressure within tolerances.", "Macro tape is quiet."],
    )
    op_b = _opinion(
        role="claude_risk_assessment_analyst",
        score=6.0,
        dynamics=[shared, "Earnings far enough away.", "Liquidity is workable."],
    )
    op_c = _opinion(
        role="deepseek_quant_assessment_analyst",
        score=6.0,
        dynamics=[
            shared,
            "Vol structure is unusually quiet here.",
            "Realised drift below the threshold.",
            "Skew unremarkable.",
        ],
    )

    consensus, _ = synthesize_assessment_consensus(
        {
            "openai_assessment_analyst": op_a,
            "claude_risk_assessment_analyst": op_b,
            "deepseek_quant_assessment_analyst": op_c,
        },
        {},
    )
    assert consensus is not None
    sentences = consensus.actual_dynamics_summary
    assert 3 <= len(sentences) <= 4
    assert sentences.count(shared) == 1


def test_skips_members_with_error() -> None:
    op_a = _opinion(role="openai_assessment_analyst", score=8.0)
    op_b = _opinion(
        role="claude_risk_assessment_analyst",
        score=0.0,
        risk="High",
        error="provider chain exhausted",
    )

    consensus, meta = synthesize_assessment_consensus(
        {
            "openai_assessment_analyst": op_a,
            "claude_risk_assessment_analyst": op_b,
        },
        {},
    )
    assert consensus is not None
    assert meta["members_valid"] == 1
    assert consensus.credit_safety_score == pytest.approx(8.0)


def test_returns_none_when_all_members_errored() -> None:
    op_a = _opinion(
        role="openai_assessment_analyst", score=0.0, error="boom"
    )
    op_b = _opinion(
        role="claude_risk_assessment_analyst", score=0.0, error="boom"
    )

    consensus, meta = synthesize_assessment_consensus(
        {
            "openai_assessment_analyst": op_a,
            "claude_risk_assessment_analyst": op_b,
        },
        {},
    )
    assert consensus is None
    assert meta["reason"] == "no_valid_members"


def test_revised_opinion_overrides_round1() -> None:
    op = _opinion(role="openai_assessment_analyst", score=4.0)
    revised = _opinion(role="openai_assessment_analyst", score=9.0)
    revision = AssessmentRevision(
        model="gpt",  # type: ignore[arg-type]
        assessment_role="openai_assessment_analyst",
        assessment_label="OpenAI Assessment Analyst",
        revised_opinion=revised,
    )

    consensus, _ = synthesize_assessment_consensus(
        {"openai_assessment_analyst": op},
        {"openai_assessment_analyst": revision},
    )
    assert consensus is not None
    assert consensus.credit_safety_score == pytest.approx(9.0)


def test_fallback_consensus_from_promotes_single_opinion() -> None:
    op = _opinion(role="openai_assessment_analyst", score=7.5)
    consensus = fallback_consensus_from(op)
    assert consensus.credit_safety_score == pytest.approx(7.5)
    assert consensus.risk == op.risk
    assert consensus.actual_dynamics_summary == op.actual_dynamics_summary
