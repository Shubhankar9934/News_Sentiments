"""Orchestrate the 3-member Reverse BWB Assessment Team."""

from __future__ import annotations

import structlog

from app.core.config import Settings
from app.services.assessment.assessment_config import get_assessment_members
from app.services.assessment.round1_independent import run_assessment_round1
from app.services.assessment.round2_critique import run_assessment_round2
from app.services.assessment.round3_revision import run_assessment_round3
from app.services.assessment.round4_consensus import (
    synthesize_assessment_consensus,
)
from app.services.assessment.schemas import AssessmentLayer
from app.services.deliberation.llm_clients.base import BaseDeliberationClient
from app.services.deliberation.schemas import IntelligencePackage
from app.services.dil_resilience.quorum import QuorumEvaluator
from app.services.dil_resilience.registry import get_resilience_gateway

log = structlog.get_logger(__name__)


async def run_assessment_team(
    intel: IntelligencePackage,
    client_map: dict[str, BaseDeliberationClient],
    settings: Settings,
) -> AssessmentLayer | None:
    """Run the 4-round assessment debate and return the merged layer.

    Returns ``None`` when the Assessment Team cannot reach the minimum
    quorum (``settings.effective_assessment_min_members``). The caller is
    expected to fall back to the deterministic projector in that case.
    """

    members = get_assessment_members(settings)
    if not members:
        return None

    log.info(
        "dil.assessment.start",
        ticker=intel.ticker,
        question=intel.question,
        members=[m.key for m in members],
    )

    round1 = await run_assessment_round1(members, client_map, intel)
    quorum = QuorumEvaluator.evaluate(
        round1,
        required=settings.effective_assessment_min_members,
        total=len(members),
    )
    gateway = get_resilience_gateway()
    gateway.metrics.record_assessment_quorum(
        valid=quorum.valid_count,
        degraded=quorum.degraded,
        quorum_met=quorum.meets_quorum,
    )

    if not quorum.meets_quorum:
        log.warning(
            "dil.assessment.insufficient_members",
            valid=quorum.valid_count,
            required=quorum.required,
        )
        return None

    if quorum.degraded:
        log.warning(
            "dil.assessment.degraded",
            valid=quorum.valid_count,
            total=quorum.total,
            failed_roles=list(quorum.failed_roles),
        )

    round2 = await run_assessment_round2(members, client_map, round1, intel)
    round3 = await run_assessment_round3(members, client_map, round1, round2, intel)
    consensus, meta = synthesize_assessment_consensus(round1, round3)
    if quorum.degraded:
        meta = {**meta, "degraded": True, "quorum": quorum.to_meta()}

    log.info(
        "dil.assessment.complete",
        ticker=intel.ticker,
        has_consensus=consensus is not None,
        members_valid=meta.get("members_valid"),
        degraded=quorum.degraded,
    )

    return AssessmentLayer(
        question=intel.question,
        trigger=intel.trigger,
        round1=round1,
        round2=round2,
        round3=round3,
        consensus=consensus,
        consensus_meta=meta,
        degraded=quorum.degraded,
        quorum_meta=quorum.to_meta(),
    )
