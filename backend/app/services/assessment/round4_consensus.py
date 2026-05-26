"""Assessment Round 4: deterministic merge into the canonical card body.

The Assessment Team's debate produces up to three independent Reverse
BWB cards (one per member) after revisions. Round 4 fuses them into a
single ``AssessmentConsensus`` row that the dashboard persists.

Merge rules:

* Numeric fields (``credit_safety_score``, expected-range ``low/high``)
  use the median across surviving opinions, rounded sensibly.
* Enum fields (``risk``, ``confidence``, outlooks, chances, pin/event
  risk, IV quality, liquidity) use the modal vote; ties resolve toward
  the more conservative bucket so the card never overstates safety.
* ``danger_zone`` is taken from the highest-risk member (longest
  string is treated as the most explicit description; pin-risk-driven
  tie-break keeps the most cautious phrasing).
* ``actual_dynamics_summary`` concatenates every member's sentences,
  deduplicates by lowercased first 80 chars, and caps at 4 entries.
"""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from app.services.assessment.schemas import (
    AssessmentMemberOpinion,
    AssessmentRevision,
)
from app.services.dashboard.schemas import (
    AssessmentConsensus,
    ChanceLabel,
    ConfidenceLevel,
    ExpectedRange,
    IvQualityLabel,
    LiquidityLabel,
    NextOutlook,
    RiskLevel,
    TodayOutlook,
)

# Conservative tie-break ordering for each enum vocabulary. When two
# candidate labels tie on count, the one that appears LATER in this
# tuple wins (i.e. more conservative for risk-style scales).
_RISK_ORDER: tuple[str, ...] = ("Low", "Medium", "High")
_CONFIDENCE_ORDER: tuple[str, ...] = ("High", "Medium", "Low")  # lower is more conservative
_TODAY_OUTLOOK_ORDER: tuple[str, ...] = ("Bullish", "Bearish", "Sideways", "Choppy")
_NEXT_OUTLOOK_ORDER: tuple[str, ...] = ("Bullish", "Bearish", "Sideways", "Volatile")
_CHANCE_ORDER: tuple[str, ...] = ("Low", "Medium", "High")
_IV_ORDER: tuple[str, ...] = ("Good", "Average", "Poor")  # lower quality is more conservative
_LIQUIDITY_ORDER: tuple[str, ...] = ("Good", "Average", "Poor")


def _final_opinions(
    round1: dict[str, AssessmentMemberOpinion],
    round3: dict[str, AssessmentRevision],
) -> list[AssessmentMemberOpinion]:
    finals: list[AssessmentMemberOpinion] = []
    for role_key, op in round1.items():
        if op.error:
            continue
        rev = round3.get(role_key)
        if rev and not rev.error and rev.revised_opinion is not None:
            finals.append(rev.revised_opinion)
        else:
            finals.append(op)
    return finals


def _modal(values: list[str], order: tuple[str, ...], fallback: str) -> str:
    """Pick the most common value; tie-break toward the more conservative end."""

    if not values:
        return fallback
    counts = Counter(values)
    top = max(counts.values())
    winners = [v for v in values if counts[v] == top]
    if len(set(winners)) == 1:
        return winners[0]
    # Tie — pick the label that appears LATER in ``order``.
    ranked = [v for v in order if v in winners]
    return ranked[-1] if ranked else winners[0]


def _median_range(values: list[tuple[float, float]]) -> ExpectedRange:
    if not values:
        return ExpectedRange(low=0.0, high=0.0)
    lows = [v[0] for v in values]
    highs = [v[1] for v in values]
    low = round(median(lows), 2)
    high = round(median(highs), 2)
    if high < low:
        low, high = high, low
    return ExpectedRange(low=low, high=high)


def _pick_danger_zone(finals: list[AssessmentMemberOpinion]) -> str:
    """Prefer the descriptor from the member whose pin_risk is highest.

    Ties go to the longest non-empty string so we keep the most explicit
    phrasing on the card.
    """

    if not finals:
        return "unavailable"
    rank = {label: idx for idx, label in enumerate(_RISK_ORDER)}
    finals_sorted = sorted(
        finals,
        key=lambda op: (rank.get(op.pin_risk, 0), len(op.danger_zone or "")),
        reverse=True,
    )
    return finals_sorted[0].danger_zone or "unavailable"


def _merge_dynamics(finals: list[AssessmentMemberOpinion]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    # Interleave member sentences so the consensus doesn't echo one voice.
    max_len = max((len(op.actual_dynamics_summary) for op in finals), default=0)
    for idx in range(max_len):
        for op in finals:
            if idx >= len(op.actual_dynamics_summary):
                continue
            sentence = (op.actual_dynamics_summary[idx] or "").strip()
            if not sentence:
                continue
            key = sentence.lower()[:80]
            if key in seen:
                continue
            seen.add(key)
            merged.append(sentence)
            if len(merged) >= 4:
                break
        if len(merged) >= 4:
            break
    # Always satisfy the AssessmentConsensus ``min_length=3`` constraint.
    while len(merged) < 3:
        merged.append("Insufficient narrative diversity across the Assessment Team.")
    return merged[:4]


def synthesize_assessment_consensus(
    round1: dict[str, AssessmentMemberOpinion],
    round3: dict[str, AssessmentRevision],
) -> tuple[AssessmentConsensus | None, dict[str, Any]]:
    """Deterministic merge of surviving Assessment Team opinions.

    Returns ``(consensus, meta)``. ``consensus`` is ``None`` when no
    members produced a valid opinion. ``meta`` carries support counts
    + agreement rates for audit.
    """

    finals = _final_opinions(round1, round3)
    meta: dict[str, Any] = {
        "members_total": len(round1),
        "members_valid": len(finals),
    }
    if not finals:
        return None, {**meta, "reason": "no_valid_members"}

    credit = round(median([op.credit_safety_score for op in finals]), 1)

    risk = _modal([op.risk for op in finals], _RISK_ORDER, "Medium")
    confidence = _modal(
        [op.confidence for op in finals], _CONFIDENCE_ORDER, "Medium"
    )
    today_outlook = _modal(
        [op.today_outlook for op in finals], _TODAY_OUTLOOK_ORDER, "Sideways"
    )
    next_3d_outlook = _modal(
        [op.next_3d_outlook for op in finals], _NEXT_OUTLOOK_ORDER, "Sideways"
    )
    chance_up = _modal(
        [op.chance_up_2_3_pct for op in finals], _CHANCE_ORDER, "Low"
    )
    chance_down = _modal(
        [op.chance_down_2_3_pct for op in finals], _CHANCE_ORDER, "Low"
    )
    pin_risk = _modal([op.pin_risk for op in finals], _RISK_ORDER, "Medium")
    event_risk = _modal([op.event_risk for op in finals], _RISK_ORDER, "Medium")
    iv_quality = _modal([op.iv_quality for op in finals], _IV_ORDER, "Average")
    liquidity = _modal([op.liquidity for op in finals], _LIQUIDITY_ORDER, "Average")

    expected_today = _median_range(
        [
            (op.expected_range_today.low, op.expected_range_today.high)
            for op in finals
        ]
    )
    expected_next = _median_range(
        [
            (op.expected_range_next_3d.low, op.expected_range_next_3d.high)
            for op in finals
        ]
    )

    danger_zone = _pick_danger_zone(finals)
    dynamics = _merge_dynamics(finals)

    consensus = AssessmentConsensus(
        credit_safety_score=credit,
        risk=risk,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        today_outlook=today_outlook,  # type: ignore[arg-type]
        next_3d_outlook=next_3d_outlook,  # type: ignore[arg-type]
        chance_up_2_3_pct=chance_up,  # type: ignore[arg-type]
        chance_down_2_3_pct=chance_down,  # type: ignore[arg-type]
        expected_range_today=expected_today,
        expected_range_next_3d=expected_next,
        danger_zone=danger_zone,
        pin_risk=pin_risk,  # type: ignore[arg-type]
        event_risk=event_risk,  # type: ignore[arg-type]
        iv_quality=iv_quality,  # type: ignore[arg-type]
        liquidity=liquidity,  # type: ignore[arg-type]
        actual_dynamics_summary=dynamics,
    )

    def _support(values: list[str], chosen: str) -> int:
        return sum(1 for v in values if v == chosen)

    meta.update(
        {
            "credit_safety_score_inputs": [op.credit_safety_score for op in finals],
            "risk_support": _support([op.risk for op in finals], risk),
            "confidence_support": _support(
                [op.confidence for op in finals], confidence
            ),
            "today_outlook_support": _support(
                [op.today_outlook for op in finals], today_outlook
            ),
            "next_3d_outlook_support": _support(
                [op.next_3d_outlook for op in finals], next_3d_outlook
            ),
        }
    )

    return consensus, meta


def fallback_consensus_from(opinion: AssessmentMemberOpinion) -> AssessmentConsensus:
    """Promote a single member opinion to a consensus when N=1.

    Used only when the deterministic projector falls back to a single
    member output (e.g. orchestrator gating). Mirrors the same field
    list as ``synthesize_assessment_consensus``.
    """

    return AssessmentConsensus(
        credit_safety_score=round(opinion.credit_safety_score, 1),
        risk=opinion.risk,
        confidence=opinion.confidence,
        today_outlook=opinion.today_outlook,
        next_3d_outlook=opinion.next_3d_outlook,
        chance_up_2_3_pct=opinion.chance_up_2_3_pct,
        chance_down_2_3_pct=opinion.chance_down_2_3_pct,
        expected_range_today=opinion.expected_range_today,
        expected_range_next_3d=opinion.expected_range_next_3d,
        danger_zone=opinion.danger_zone,
        pin_risk=opinion.pin_risk,
        event_risk=opinion.event_risk,
        iv_quality=opinion.iv_quality,
        liquidity=opinion.liquidity,
        actual_dynamics_summary=opinion.actual_dynamics_summary,
    )


__all__ = [
    "AssessmentConsensus",
    "ChanceLabel",
    "ConfidenceLevel",
    "IvQualityLabel",
    "LiquidityLabel",
    "NextOutlook",
    "RiskLevel",
    "TodayOutlook",
    "fallback_consensus_from",
    "synthesize_assessment_consensus",
]
