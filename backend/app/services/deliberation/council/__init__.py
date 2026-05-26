"""Orchestrate the full Decision Council debate."""

from __future__ import annotations

import structlog

from app.core.config import Settings
from app.services.deliberation.council.council_config import get_council_members
from app.services.deliberation.council.round1_independent import run_council_round1
from app.services.deliberation.council.round2_critique import run_council_round2
from app.services.deliberation.council.round3_revision import run_council_round3
from app.services.deliberation.council.round4_consensus import synthesize_council_consensus
from app.services.deliberation.llm_clients.base import BaseDeliberationClient
from app.services.deliberation.schemas import CouncilLayer, IntelligencePackage
from app.services.dil_resilience.quorum import QuorumEvaluator
from app.services.dil_resilience.registry import get_resilience_gateway

log = structlog.get_logger(__name__)


async def run_decision_council(
    intel: IntelligencePackage,
    client_map: dict[str, BaseDeliberationClient],
    settings: Settings,
) -> CouncilLayer | None:
    members = get_council_members(settings)
    if not members:
        return None

    log.info("dil.council.start", question=intel.question, trigger=intel.trigger)

    round1 = await run_council_round1(members, client_map, intel)
    quorum = QuorumEvaluator.evaluate(
        round1,
        required=settings.effective_council_min_members,
        total=len(members),
    )
    gateway = get_resilience_gateway()
    gateway.metrics.record_council_quorum(
        valid=quorum.valid_count,
        degraded=quorum.degraded,
        quorum_met=quorum.meets_quorum,
    )

    if not quorum.meets_quorum:
        log.warning(
            "dil.council.insufficient_members",
            valid=quorum.valid_count,
            required=quorum.required,
        )
        return None

    if quorum.degraded:
        log.warning(
            "dil.council.degraded",
            valid=quorum.valid_count,
            total=quorum.total,
            failed_roles=list(quorum.failed_roles),
        )

    round2 = await run_council_round2(members, client_map, round1, intel)
    round3 = await run_council_round3(members, client_map, round1, round2, intel)
    consensus = synthesize_council_consensus(
        round1, round2, round3, degraded=quorum.degraded, quorum=quorum
    )

    log.info(
        "dil.council.complete",
        decision=consensus.decision,
        support=consensus.support,
        confidence=consensus.confidence,
        degraded=quorum.degraded,
    )

    return CouncilLayer(
        question=intel.question,
        trigger=intel.trigger,
        round1=round1,
        round2=round2,
        round3=round3,
        consensus=consensus,
        degraded=quorum.degraded,
        quorum_meta=quorum.to_meta(),
    )
