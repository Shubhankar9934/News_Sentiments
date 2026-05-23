"""Debate round 1: cross-critique."""

from __future__ import annotations

import asyncio
import json

import structlog

from app.services.deliberation.debate.routing import (
    DebateAssignment,
    assignment_for,
    build_assignments,
)
from app.services.deliberation.llm_clients.base import (
    BaseDeliberationClient,
    load_prompt,
    parse_strict_json,
)
from app.services.deliberation.schemas import DebateCritique, IndependentOpinion, ModelKey

log = structlog.get_logger(__name__)


def _summarize_others(
    self_model: ModelKey,
    round1: dict[str, IndependentOpinion],
) -> list[dict]:
    summaries = []
    for model, op in round1.items():
        if model == self_model or op.error:
            continue
        summaries.append(
            {
                "model": model,
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
    """Ensure the model's response actually critiques its assigned targets.

    The LLM is free to also engage extras, but every target must show up in
    either ``agrees_with`` or ``disagrees_with`` so the routing has bite.
    Devil's-advocate role implies the model must register at least one
    disagree edge (it cannot silently nod along).
    """
    if assignment is None:
        return critique

    mentioned: set[str] = set(critique.agrees_with) | set(critique.disagrees_with)
    for target in assignment.targets:
        if target not in mentioned:
            critique.disagrees_with = list(critique.disagrees_with) + [target]
            mentioned.add(target)
    if assignment.role == "devils_advocate" and not critique.disagrees_with:
        # Devil's advocate must register dissent; promote first target.
        if assignment.targets:
            critique.disagrees_with = [assignment.targets[0]]
    return critique


async def _critique_one(
    client: BaseDeliberationClient,
    round1: dict[str, IndependentOpinion],
    assignment: DebateAssignment | None,
) -> tuple[ModelKey, DebateCritique]:
    own = round1.get(client.model_key)
    if not own or own.error:
        return client.model_key, DebateCritique(
            model=client.model_key,
            error="skipped — no valid round1 opinion",
        )
    system = load_prompt("critique.txt")
    others = _summarize_others(client.model_key, round1)
    assignment_payload: dict = {}
    if assignment is not None:
        assignment_payload = {
            "assigned_targets": assignment.targets,
            "assigned_role": assignment.role,
            "rationale": assignment.rationale,
        }
    user = (
        f"Your prior opinion:\n{json.dumps(own.model_dump(), indent=2)}\n\n"
        f"Other models (summarized):\n{json.dumps(others, indent=2)}\n\n"
        f"Routing for this round:\n{json.dumps(assignment_payload, indent=2)}\n\n"
        f'Return JSON with "model" set to "{client.model_key}". '
        f"confidence_revision.old must be {own.confidence}."
    )
    try:
        raw = await client.complete_json(system, user)
        critique = parse_strict_json(raw, DebateCritique)
        critique.model = client.model_key
        if critique.confidence_revision is None:
            critique.confidence_revision = None
        elif critique.confidence_revision.old != own.confidence:
            critique.confidence_revision.old = own.confidence
        critique = _enforce_assignment(critique, assignment)
        return client.model_key, critique
    except Exception as e:
        log.warning("dil.debate1.model_failed", model=client.model_key, error=str(e))
        return client.model_key, DebateCritique(model=client.model_key, error=str(e))


async def run_cross_critique(
    clients: list[BaseDeliberationClient],
    round1: dict[str, IndependentOpinion],
    *,
    use_routing: bool = True,
    round_index: int = 1,
) -> tuple[dict[str, DebateCritique], list[DebateAssignment]]:
    assignments: list[DebateAssignment] = []
    if use_routing:
        assignments = build_assignments(round_index, round1)
    results = await asyncio.gather(
        *[
            _critique_one(c, round1, assignment_for(assignments, c.model_key))
            for c in clients
        ]
    )
    return dict(results), assignments
