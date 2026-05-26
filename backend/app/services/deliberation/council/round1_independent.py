"""Council Round 1: independent decisions from intelligence package."""

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
    CouncilMemberDecision,
    CouncilRoleKey,
    IntelligencePackage,
    TradeDecision,
)

log = structlog.get_logger(__name__)


async def _run_one_member(
    member: CouncilMemberDefinition,
    client_map: dict[str, BaseDeliberationClient],
    intel: IntelligencePackage,
) -> tuple[CouncilRoleKey, CouncilMemberDecision]:
    role_key = member.key
    role_label = member.label

    async def _call(client: BaseDeliberationClient) -> CouncilMemberDecision:
        system = load_prompt("council/council_decision.txt")
        role_prompt = load_council_prompt(role_key)
        if role_prompt:
            system = f"{system}\n\n{role_prompt}"

        intel_payload = intel.model_dump(mode="json")
        assessment_note = ""
        if intel.assessment_consensus:
            assessment_note = (
                "\n\nThe Reverse BWB Assessment Team has already produced "
                "the card body for this ticker (every field EXCEPT the "
                "trade decision). Treat the values below as the "
                "authoritative reading of the market state and base your "
                "ENTER / WAIT / AVOID call on them.\n"
                f"AssessmentConsensus:\n"
                f"{json.dumps(intel.assessment_consensus, indent=2, default=str)}"
            )
        user = (
            f"Decision question: {intel.question}\n"
            f"Trigger: {intel.trigger}\n"
            f"Council role: {role_label}\n\n"
            f"Intelligence package:\n"
            f"{json.dumps(intel_payload, indent=2, default=str)}"
            f"{assessment_note}\n\n"
            f'Return JSON with "model" set to "{client.model_key}", '
            f'"council_role": "{role_key}", "council_label": "{role_label}".'
        )
        raw = await client.complete_json(system, user)
        decision = parse_strict_json(raw, CouncilMemberDecision)
        decision.model = client.model_key  # type: ignore[assignment]
        decision.council_role = role_key
        decision.council_label = role_label
        return decision

    provider, attempts, result, err = await execute_council_member(
        member, client_map, _call
    )
    if result is not None and provider is not None:
        result.provider_attempts = attempts
        return role_key, result

    log.warning("dil.council.round1.failed", role=role_key, error=err)
    return role_key, CouncilMemberDecision(
        model=(provider or member.primary),
        council_role=role_key,
        council_label=role_label,
        decision="WAIT",
        confidence=0.0,
        error=err or "No provider available",
        provider_attempts=attempts,
    )


async def run_council_round1(
    members: list[CouncilMemberDefinition],
    client_map: dict[str, BaseDeliberationClient],
    intel: IntelligencePackage,
) -> dict[str, CouncilMemberDecision]:
    batch = await asyncio.gather(
        *[_run_one_member(m, client_map, intel) for m in members]
    )
    return dict(batch)
