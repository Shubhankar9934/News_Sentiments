"""Council Round 3: revision after peer critique."""

from __future__ import annotations

import asyncio
import json

import structlog

from app.services.deliberation.council.council_config import CouncilMemberDefinition
from app.services.deliberation.council.council_executor import execute_council_member
from app.services.deliberation.llm_clients.base import (
    BaseDeliberationClient,
    load_council_prompt,
    load_prompt,
    parse_strict_json,
)
from app.services.deliberation.schemas import (
    CouncilCritique,
    CouncilMemberDecision,
    CouncilRevision,
    CouncilRoleKey,
    IntelligencePackage,
)

log = structlog.get_logger(__name__)


async def _revise_one(
    member: CouncilMemberDefinition,
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, CouncilMemberDecision],
    round2: dict[str, CouncilCritique],
    intel: IntelligencePackage,
) -> tuple[CouncilRoleKey, CouncilRevision]:
    role_key = member.key
    own = round1.get(role_key)
    critique = round2.get(role_key)
    if not own or own.error:
        return role_key, CouncilRevision(
            model=member.primary,
            council_role=role_key,
            council_label=member.label,
            prior_decision="WAIT",
            revised_decision="WAIT",
            prior_confidence=0.0,
            revised_confidence=0.0,
            error="Missing Round 1 decision",
        )

    async def _call(client: BaseDeliberationClient) -> CouncilRevision:
        system = load_prompt("council/council_revision.txt")
        role_prompt = load_council_prompt(role_key)
        if role_prompt:
            system = f"{system}\n\n{role_prompt}"

        peer_critiques = {
            k: v.model_dump()
            for k, v in round2.items()
            if k != role_key and not v.error
        }
        user = (
            f"Decision question: {intel.question}\n"
            f"Your role: {member.label}\n\n"
            f"Your Round 1 decision:\n{json.dumps(own.model_dump(), indent=2, default=str)}\n\n"
            f"Critiques of your decision:\n{json.dumps(peer_critiques, indent=2, default=str)}\n\n"
            f'Return JSON with council_role="{role_key}", council_label="{member.label}".'
        )
        raw = await client.complete_json(system, user)
        revision = parse_strict_json(raw, CouncilRevision)
        revision.model = client.model_key  # type: ignore[assignment]
        revision.council_role = role_key
        revision.council_label = member.label
        if not revision.prior_decision:
            revision.prior_decision = own.decision
        if revision.revised_confidence == 0.0 and revision.prior_confidence == 0.0:
            revision.prior_confidence = own.confidence
        return revision

    _, _, result, err = await execute_council_member(member, client_map, _call)
    if result is not None:
        return role_key, result

    return role_key, CouncilRevision(
        model=member.primary,
        council_role=role_key,
        council_label=member.label,
        prior_decision=own.decision,
        revised_decision=own.decision,
        prior_confidence=own.confidence,
        revised_confidence=own.confidence,
        revision_rationale="No revision — provider failed",
        error=err,
    )


async def run_council_round3(
    members: list[CouncilMemberDefinition],
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, CouncilMemberDecision],
    round2: dict[str, CouncilCritique],
    intel: IntelligencePackage,
) -> dict[str, CouncilRevision]:
    batch = await asyncio.gather(
        *[_revise_one(m, client_map, round1, round2, intel) for m in members]
    )
    return dict(batch)
