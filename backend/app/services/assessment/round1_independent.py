"""Assessment Round 1: each member emits a full Reverse BWB card.

Round 1 is the only place where each Assessment member proposes the
full card body from the unified intelligence package. Rounds 2-3 are
critique + revision; Round 4 deterministically merges the surviving
opinions into the canonical ``AssessmentConsensus``.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from app.services.assessment.assessment_config import AssessmentMemberDefinition
from app.services.assessment.assessment_executor import execute_assessment_member
from app.services.assessment.prompt_loader import (
    load_assessment_prompt,
    load_assessment_role_prompt,
)
from app.services.assessment.schemas import AssessmentMemberOpinion
from app.services.deliberation.llm_clients.base import (
    BaseDeliberationClient,
    parse_strict_json,
)
from app.services.deliberation.schemas import AssessmentRoleKey, IntelligencePackage

log = structlog.get_logger(__name__)


def _build_user_message(
    member: AssessmentMemberDefinition,
    intel: IntelligencePackage,
) -> str:
    """Slim, structured intel for the Assessment Team.

    Pass only the desk findings + options snapshot + ticker — never the
    raw report. Keeps tokens predictable and forces the LLM to ground
    every field in the structured data we pass in.
    """

    desks_view: dict[str, Any] = {}
    for desk_key, desk in intel.desks.items():
        if desk.error:
            continue
        desks_view[desk_key] = {
            "role_label": desk.role_label,
            "model": desk.model,
            "analytical_view": desk.analytical_view,
            "confidence_in_analysis": desk.confidence_in_analysis,
            "key_findings": desk.key_findings[:6],
            "metrics": desk.metrics,
            "risks": desk.risks[:6],
            "invalidators": desk.invalidators[:4],
        }

    payload = {
        "ticker": intel.ticker,
        "question": intel.question,
        "options_snapshot": intel.options_snapshot,
        "credit_safety": intel.credit_safety,
        "desks": desks_view,
    }

    return (
        f"Ticker: {intel.ticker}\n"
        f"Assessment role: {member.label}\n\n"
        "Produce the Reverse BWB Credit View card body for this ticker. "
        "Use ONLY the structured intelligence below. Do not invent numbers; "
        "every field must trace to the desks or the options snapshot.\n\n"
        f"Intelligence package:\n{json.dumps(payload, indent=2, default=str)}\n\n"
        f'Return JSON with "model" set to "{member.primary}", '
        f'"assessment_role": "{member.key}", '
        f'"assessment_label": "{member.label}".'
    )


async def _run_one_member(
    member: AssessmentMemberDefinition,
    client_map: dict[str, BaseDeliberationClient],
    intel: IntelligencePackage,
) -> tuple[AssessmentRoleKey, AssessmentMemberOpinion]:
    role_key = member.key
    role_label = member.label

    async def _call(client: BaseDeliberationClient) -> AssessmentMemberOpinion:
        system = load_assessment_prompt("assessment_independent.txt")
        role_prompt = load_assessment_role_prompt(role_key)
        if role_prompt:
            system = f"{system}\n\n{role_prompt}"

        user = _build_user_message(member, intel)
        raw = await client.complete_json(system, user)
        opinion = parse_strict_json(raw, AssessmentMemberOpinion)
        opinion.model = client.model_key  # type: ignore[assignment]
        opinion.assessment_role = role_key
        opinion.assessment_label = role_label
        return opinion

    provider, attempts, result, err = await execute_assessment_member(
        member, client_map, _call
    )
    if result is not None and provider is not None:
        result.provider_attempts = attempts
        return role_key, result

    log.warning("dil.assessment.round1.failed", role=role_key, error=err)
    return role_key, _empty_opinion_with_error(member, attempts, err)


def _empty_opinion_with_error(
    member: AssessmentMemberDefinition,
    attempts: list[str],
    err: str | None,
) -> AssessmentMemberOpinion:
    """Pydantic still requires valid Literals — emit defensible defaults + error."""

    from app.services.dashboard.schemas import ExpectedRange

    return AssessmentMemberOpinion(
        model=member.primary,
        assessment_role=member.key,
        assessment_label=member.label,
        credit_safety_score=0.0,
        risk="High",
        confidence="Low",
        today_outlook="Sideways",
        next_3d_outlook="Sideways",
        chance_up_2_3_pct="Low",
        chance_down_2_3_pct="Low",
        expected_range_today=ExpectedRange(low=0.0, high=0.0),
        expected_range_next_3d=ExpectedRange(low=0.0, high=0.0),
        danger_zone="unavailable",
        pin_risk="Medium",
        event_risk="Medium",
        iv_quality="Average",
        liquidity="Average",
        actual_dynamics_summary=[
            "Assessment member could not run.",
            "Provider chain exhausted without a usable response.",
            "Card body will fall back to the deterministic projector.",
        ],
        provider_attempts=attempts,
        error=err or "No provider available",
    )


async def run_assessment_round1(
    members: list[AssessmentMemberDefinition],
    client_map: dict[str, BaseDeliberationClient],
    intel: IntelligencePackage,
) -> dict[str, AssessmentMemberOpinion]:
    batch = await asyncio.gather(
        *[_run_one_member(m, client_map, intel) for m in members]
    )
    return dict(batch)
