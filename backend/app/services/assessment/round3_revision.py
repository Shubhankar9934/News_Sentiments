"""Assessment Round 3: each member revises its Round 1 card after peer critique."""

from __future__ import annotations

import asyncio
import json

import structlog

from app.services.assessment.assessment_config import AssessmentMemberDefinition
from app.services.assessment.assessment_executor import execute_assessment_member
from app.services.assessment.prompt_loader import (
    load_assessment_prompt,
    load_assessment_role_prompt,
)
from app.services.assessment.schemas import (
    AssessmentCritique,
    AssessmentMemberOpinion,
    AssessmentRevision,
)
from app.services.deliberation.llm_clients.base import (
    BaseDeliberationClient,
    parse_strict_json,
)
from app.services.deliberation.schemas import AssessmentRoleKey, IntelligencePackage

log = structlog.get_logger(__name__)


async def _revise_one(
    member: AssessmentMemberDefinition,
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, AssessmentMemberOpinion],
    round2: dict[str, AssessmentCritique],
    intel: IntelligencePackage,
) -> tuple[AssessmentRoleKey, AssessmentRevision]:
    role_key = member.key
    own = round1.get(role_key)
    if not own or own.error:
        return role_key, AssessmentRevision(
            model=member.primary,
            assessment_role=role_key,
            assessment_label=member.label,
            error="Missing Round 1 opinion",
        )

    async def _call(client: BaseDeliberationClient) -> AssessmentRevision:
        system = load_assessment_prompt("assessment_revision.txt")
        role_prompt = load_assessment_role_prompt(role_key)
        if role_prompt:
            system = f"{system}\n\n{role_prompt}"

        peer_critiques = {
            k: v.model_dump()
            for k, v in round2.items()
            if k != role_key and not v.error
        }
        user = (
            f"Ticker: {intel.ticker}\n"
            f"Your role: {member.label}\n\n"
            f"Your Round 1 card:\n{json.dumps(own.model_dump(), indent=2, default=str)}\n\n"
            "Critiques of your card from peers:\n"
            f"{json.dumps(peer_critiques, indent=2, default=str)}\n\n"
            f'Return JSON with assessment_role="{role_key}", '
            f'assessment_label="{member.label}".'
        )
        raw = await client.complete_json(system, user)
        revision = parse_strict_json(raw, AssessmentRevision)
        revision.model = client.model_key  # type: ignore[assignment]
        revision.assessment_role = role_key
        revision.assessment_label = member.label
        if revision.revised_opinion is not None:
            revision.revised_opinion.assessment_role = role_key
            revision.revised_opinion.assessment_label = member.label
            revision.revised_opinion.model = client.model_key  # type: ignore[assignment]
        return revision

    provider, attempts, result, err = await execute_assessment_member(
        member, client_map, _call
    )
    if result is not None and provider is not None:
        result.provider_attempts = attempts
        return role_key, result

    log.warning("dil.assessment.round3.failed", role=role_key, error=err)
    return role_key, AssessmentRevision(
        model=member.primary,
        assessment_role=role_key,
        assessment_label=member.label,
        provider_attempts=attempts,
        revision_rationale="No revision — provider failed",
        error=err or "Revision failed",
    )


async def run_assessment_round3(
    members: list[AssessmentMemberDefinition],
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, AssessmentMemberOpinion],
    round2: dict[str, AssessmentCritique],
    intel: IntelligencePackage,
) -> dict[str, AssessmentRevision]:
    batch = await asyncio.gather(
        *[_revise_one(m, client_map, round1, round2, intel) for m in members]
    )
    return dict(batch)
