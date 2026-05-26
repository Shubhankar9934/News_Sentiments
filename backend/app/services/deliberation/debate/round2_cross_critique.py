"""Debate round 1: cross-critique — desk-aware."""

from __future__ import annotations

import asyncio
import json

import structlog

from app.services.deliberation.debate.routing import (
    DebateAssignment,
    assignment_for,
    build_assignments,
)
from app.services.deliberation.debate.round1_independent import client_for_desk
from app.services.deliberation.desk_config import DeskDefinition
from app.services.deliberation.llm_clients.base import (
    BaseDeliberationClient,
    load_prompt,
    load_role_prompt,
    parse_strict_json,
)
from app.services.deliberation.schemas import DebateCritique, IndependentOpinion

log = structlog.get_logger(__name__)


def _summarize_others(
    self_desk: str,
    round1: dict[str, IndependentOpinion],
) -> list[dict]:
    summaries = []
    for desk_key, op in round1.items():
        if desk_key == self_desk or op.error:
            continue
        summaries.append(
            {
                "desk_key": desk_key,
                "role_label": op.role_label or desk_key,
                "model": op.model,
                "stance": op.stance,
                "confidence": op.confidence,
                "time_horizon": op.time_horizon,
                "key_risks": op.key_risks[:5],
                "position_size_suggestion": op.position_size_suggestion,
                "reasoning_titles": [s.title for s in op.reasoning_steps[:5]],
            }
        )
    return summaries


def _enforce_assignment(
    critique: DebateCritique,
    assignment: DebateAssignment | None,
) -> DebateCritique:
    if assignment is None:
        return critique

    mentioned: set[str] = set(critique.agrees_with) | set(critique.disagrees_with)
    for target in assignment.targets:
        if target not in mentioned:
            critique.disagrees_with = list(critique.disagrees_with) + [target]
            mentioned.add(target)
    if assignment.role == "debate_devils_advocate" and not critique.disagrees_with:
        if assignment.targets:
            critique.disagrees_with = [assignment.targets[0]]
    return critique


async def _critique_one(
    desk_key: str,
    client: BaseDeliberationClient,
    round1: dict[str, IndependentOpinion],
    assignment: DebateAssignment | None,
    *,
    use_roles: bool,
) -> tuple[str, DebateCritique]:
    own = round1.get(desk_key)
    if not own or own.error:
        return desk_key, DebateCritique(
            model=client.model_key,
            role_key=desk_key,
            role_label=own.role_label if own else None,
            error="skipped — no valid round1 opinion",
        )

    system = load_prompt("critique.txt")
    if use_roles:
        role_prompt = load_role_prompt(desk_key)
        if role_prompt:
            system = f"{system}\n\n--- Your desk role during critique ---\n{role_prompt[:800]}"

    others = _summarize_others(desk_key, round1)
    assignment_payload: dict = {}
    if assignment is not None:
        assignment_payload = {
            "assigned_targets": assignment.targets,
            "assigned_role": assignment.role,
            "rationale": assignment.rationale,
        }
    user = (
        f"Your prior opinion (desk: {own.role_label or desk_key}):\n"
        f"{json.dumps(own.model_dump(), indent=2)}\n\n"
        f"Other desks (summarized):\n{json.dumps(others, indent=2)}\n\n"
        f"Routing for this round:\n{json.dumps(assignment_payload, indent=2)}\n\n"
        f'Return JSON with "model" set to "{client.model_key}", '
        f'"role_key" set to "{desk_key}". '
        f"agrees_with and disagrees_with must list desk_key values (not provider names). "
        f"confidence_revision.old must be {own.confidence}."
    )
    try:
        raw = await client.complete_json(system, user)
        critique = parse_strict_json(raw, DebateCritique)
        critique.model = client.model_key
        critique.role_key = critique.role_key or desk_key
        critique.role_label = critique.role_label or own.role_label
        if critique.confidence_revision and critique.confidence_revision.old != own.confidence:
            critique.confidence_revision.old = own.confidence
        critique = _enforce_assignment(critique, assignment)
        return desk_key, critique
    except Exception as e:
        log.warning("dil.debate1.desk_failed", desk=desk_key, error=str(e))
        return desk_key, DebateCritique(
            model=client.model_key,
            role_key=desk_key,
            role_label=own.role_label,
            error=str(e),
        )


async def run_cross_critique(
    desks: list[DeskDefinition],
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, IndependentOpinion],
    *,
    use_routing: bool = True,
    round_index: int = 1,
    use_roles: bool = True,
) -> tuple[dict[str, DebateCritique], list[DebateAssignment]]:
    assignments: list[DebateAssignment] = []
    if use_routing:
        assignments = build_assignments(round_index, round1)

    desk_by_key = {d.key: d for d in desks}
    tasks = []
    for desk_key, opinion in round1.items():
        if opinion.error:
            continue
        desk = desk_by_key.get(desk_key)
        client = client_for_desk(opinion, client_map, desk)
        if client is None:
            continue
        tasks.append(
            _critique_one(
                desk_key,
                client,
                round1,
                assignment_for(assignments, desk_key),
                use_roles=use_roles,
            )
        )

    results = await asyncio.gather(*tasks)
    return dict(results), assignments
