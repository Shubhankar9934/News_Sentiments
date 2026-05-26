"""Assessment Round 2: peers critique each other's Round 1 cards."""

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
)
from app.services.deliberation.llm_clients.base import (
    BaseDeliberationClient,
    parse_strict_json,
)
from app.services.deliberation.schemas import AssessmentRoleKey, IntelligencePackage

log = structlog.get_logger(__name__)


def _summarize_peers(
    self_role: AssessmentRoleKey,
    round1: dict[str, AssessmentMemberOpinion],
) -> list[dict]:
    summaries = []
    for role_key, op in round1.items():
        if role_key == self_role or op.error:
            continue
        summaries.append(
            {
                "assessment_role": role_key,
                "assessment_label": op.assessment_label,
                "model": op.model,
                "credit_safety_score": op.credit_safety_score,
                "risk": op.risk,
                "confidence": op.confidence,
                "today_outlook": op.today_outlook,
                "next_3d_outlook": op.next_3d_outlook,
                "chance_up_2_3_pct": op.chance_up_2_3_pct,
                "chance_down_2_3_pct": op.chance_down_2_3_pct,
                "expected_range_today": op.expected_range_today.model_dump(),
                "expected_range_next_3d": op.expected_range_next_3d.model_dump(),
                "danger_zone": op.danger_zone,
                "pin_risk": op.pin_risk,
                "event_risk": op.event_risk,
                "iv_quality": op.iv_quality,
                "liquidity": op.liquidity,
                "actual_dynamics_summary": op.actual_dynamics_summary,
            }
        )
    return summaries


async def _critique_one(
    member: AssessmentMemberDefinition,
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, AssessmentMemberOpinion],
    intel: IntelligencePackage,
) -> tuple[AssessmentRoleKey, AssessmentCritique]:
    role_key = member.key
    own = round1.get(role_key)
    if not own or own.error:
        return role_key, AssessmentCritique(
            model=member.primary,
            assessment_role=role_key,
            assessment_label=member.label,
            error="Missing own Round 1 opinion",
        )

    async def _call(client: BaseDeliberationClient) -> AssessmentCritique:
        system = load_assessment_prompt("assessment_critique.txt")
        role_prompt = load_assessment_role_prompt(role_key)
        if role_prompt:
            system = f"{system}\n\n{role_prompt}"

        user = (
            f"Ticker: {intel.ticker}\n"
            f"Your role: {member.label}\n\n"
            f"Your Round 1 card:\n{json.dumps(own.model_dump(), indent=2, default=str)}\n\n"
            "Peer Round 1 cards:\n"
            f"{json.dumps(_summarize_peers(role_key, round1), indent=2, default=str)}\n\n"
            f'Return JSON with assessment_role="{role_key}", '
            f'assessment_label="{member.label}".'
        )
        raw = await client.complete_json(system, user)
        critique = parse_strict_json(raw, AssessmentCritique)
        critique.model = client.model_key  # type: ignore[assignment]
        critique.assessment_role = role_key
        critique.assessment_label = member.label
        return critique

    provider, attempts, result, err = await execute_assessment_member(
        member, client_map, _call
    )
    if result is not None and provider is not None:
        result.provider_attempts = attempts
        return role_key, result

    log.warning("dil.assessment.round2.failed", role=role_key, error=err)
    return role_key, AssessmentCritique(
        model=member.primary,
        assessment_role=role_key,
        assessment_label=member.label,
        provider_attempts=attempts,
        error=err or "Critique failed",
    )


async def run_assessment_round2(
    members: list[AssessmentMemberDefinition],
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, AssessmentMemberOpinion],
    intel: IntelligencePackage,
) -> dict[str, AssessmentCritique]:
    batch = await asyncio.gather(
        *[_critique_one(m, client_map, round1, intel) for m in members]
    )
    return dict(batch)
