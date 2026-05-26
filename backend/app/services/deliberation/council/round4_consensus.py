"""Council Round 4: deterministic consensus from revised decisions."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from app.services.deliberation.schemas import (
    CouncilConsensus,
    CouncilMemberDecision,
    CouncilRevision,
    TradeDecision,
)

if TYPE_CHECKING:
    from app.services.dil_resilience.quorum import QuorumResult

DECISION_ORDER: tuple[TradeDecision, ...] = ("ENTER", "WAIT", "AVOID")
TIE_BREAK: TradeDecision = "WAIT"


def _final_decisions(
    round1: dict[str, CouncilMemberDecision],
    round3: dict[str, CouncilRevision],
) -> dict[str, TradeDecision]:
    finals: dict[str, TradeDecision] = {}
    for role_key, dec in round1.items():
        if dec.error:
            continue
        rev = round3.get(role_key)
        if rev and not rev.error:
            finals[role_key] = rev.revised_decision
        else:
            finals[role_key] = dec.decision
    return finals


def _main_conflict(
    round1: dict[str, CouncilMemberDecision],
    round2: dict,
    finals: dict[str, TradeDecision],
) -> str:
    decisions = list(finals.values())
    if not decisions:
        return "Insufficient council participation"
    counts = Counter(decisions)
    if len(counts) <= 1:
        return "No significant disagreement"

    enter_n = counts.get("ENTER", 0)
    avoid_n = counts.get("AVOID", 0)
    wait_n = counts.get("WAIT", 0)

    if enter_n > 0 and avoid_n > 0:
        return "premium attractiveness vs failure scenarios"
    if enter_n > 0 and wait_n > 0:
        return "edge clarity vs timing uncertainty"
    if avoid_n > 0 and wait_n > 0:
        return "risk avoidance vs wait-for-confirmation"
    return "mixed council views on risk/reward"


def synthesize_council_consensus(
    round1: dict[str, CouncilMemberDecision],
    round2: dict,
    round3: dict[str, CouncilRevision],
    *,
    degraded: bool = False,
    quorum: QuorumResult | None = None,
) -> CouncilConsensus:
    finals = _final_decisions(round1, round3)
    valid_round1 = {k: v for k, v in round1.items() if not v.error}

    if not finals:
        return CouncilConsensus(
            decision=TIE_BREAK,
            support={TIE_BREAK: 0},
            confidence=0.0,
            main_conflict="No valid council decisions",
            debate_summary="Council failed to produce decisions.",
            member_decisions=valid_round1,
        )

    support = Counter(finals.values())
    support_dict = {k: support[k] for k in DECISION_ORDER if support[k] > 0}

    max_count = max(support.values())
    winners = [d for d in DECISION_ORDER if support[d] == max_count]
    decision: TradeDecision = winners[0] if len(winners) == 1 else TIE_BREAK

    confidences = []
    for role_key, dec in valid_round1.items():
        rev = round3.get(role_key)
        if rev and not rev.error:
            confidences.append(rev.revised_confidence)
        else:
            confidences.append(dec.confidence)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    if degraded:
        avg_confidence *= 0.85

    agreement = max_count / len(finals) if finals else 0.0
    conflict = _main_conflict(round1, round2, finals)
    if degraded and quorum is not None:
        conflict = (
            f"Partial council — {quorum.valid_count}/{quorum.total} members; "
            f"{conflict}"
        )

    debate_summary = (
        f"{len(finals)} council members deliberated across 3 debate rounds. "
        f"Final vote: {decision} ({max_count}/{len(finals)}). "
        f"Support: {support_dict}. Agreement {agreement:.0%}."
    )
    if degraded and quorum is not None:
        debate_summary = (
            f"[Degraded quorum {quorum.valid_count}/{quorum.total}] "
            + debate_summary
        )

    return CouncilConsensus(
        decision=decision,
        support=support_dict,
        confidence=round(avg_confidence, 2),
        main_conflict=conflict,
        debate_summary=debate_summary,
        member_decisions=valid_round1,
    )
