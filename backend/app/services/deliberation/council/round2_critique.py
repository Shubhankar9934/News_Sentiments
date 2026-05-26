"""Council Round 2: cross-critique of peer decisions."""

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
    CouncilRoleKey,
    IntelligencePackage,
)

log = structlog.get_logger(__name__)


def _summarize_peers(
    self_role: CouncilRoleKey,
    round1: dict[str, CouncilMemberDecision],
) -> list[dict]:
    summaries = []
    for role_key, dec in round1.items():
        if role_key == self_role or dec.error:
            continue
        summaries.append(
            {
                "council_role": role_key,
                "council_label": dec.council_label,
                "model": dec.model,
                "decision": dec.decision,
                "confidence": dec.confidence,
                "key_risks": dec.key_risks[:5],
                "reasoning_titles": [s.title for s in dec.reasoning_steps[:5]],
            }
        )
    return summaries


async def _critique_one(
    member: CouncilMemberDefinition,
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, CouncilMemberDecision],
    intel: IntelligencePackage,
) -> tuple[CouncilRoleKey, CouncilCritique]:
    role_key = member.key
    own = round1.get(role_key)
    if not own or own.error:
        return role_key, CouncilCritique(
            model=member.primary,
            council_role=role_key,
            council_label=member.label,
            error="Missing own Round 1 decision",
        )

    client = client_map.get(own.model) or client_map.get(member.primary)
    if client is None:
        return role_key, CouncilCritique(
            model=member.primary,
            council_role=role_key,
            council_label=member.label,
            error="No client available",
        )

    async def _call(c: BaseDeliberationClient) -> CouncilCritique:
        system = load_prompt("council/council_critique.txt")
        role_prompt = load_council_prompt(role_key)
        if role_prompt:
            system = f"{system}\n\n{role_prompt}"

        user = (
            f"Decision question: {intel.question}\n"
            f"Your role: {member.label}\n\n"
            f"Your Round 1 decision:\n{json.dumps(own.model_dump(), indent=2, default=str)}\n\n"
            f"Peer decisions:\n{json.dumps(_summarize_peers(role_key, round1), indent=2)}\n\n"
            f'Return JSON with council_role="{role_key}", council_label="{member.label}".'
        )
        raw = await c.complete_json(system, user)
        critique = parse_strict_json(raw, CouncilCritique)
        critique.model = c.model_key  # type: ignore[assignment]
        critique.council_role = role_key
        critique.council_label = member.label
        return critique

    _, _, result, err = await execute_council_member(member, client_map, _call)
    if result is not None:
        return role_key, result

    return role_key, CouncilCritique(
        model=member.primary,
        council_role=role_key,
        council_label=member.label,
        error=err or "Critique failed",
    )


async def run_council_round2(
    members: list[CouncilMemberDefinition],
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, CouncilMemberDecision],
    intel: IntelligencePackage,
) -> dict[str, CouncilCritique]:
    batch = await asyncio.gather(
        *[_critique_one(m, client_map, round1, intel) for m in members]
    )
    return dict(batch)
