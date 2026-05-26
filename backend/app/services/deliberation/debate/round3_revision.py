"""Debate round 2: final revision — desk-aware."""

from __future__ import annotations

import asyncio
import json

import structlog

from app.core.config import settings as global_settings
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


def _summarize_peer_critiques(
    self_desk: str,
    debate1: dict[str, DebateCritique],
) -> list[dict]:
    out: list[dict] = []
    for other_desk, critique in debate1.items():
        if other_desk == self_desk or critique.error:
            continue
        agreed = self_desk in (critique.agrees_with or [])
        disagreed = self_desk in (critique.disagrees_with or [])
        if not agreed and not disagreed:
            continue
        out.append(
            {
                "from_desk": other_desk,
                "stance_toward_you": "agree" if agreed else "disagree",
                "their_counterargument": critique.strongest_counterargument or "",
                "their_weak_logic_claim": critique.weakest_reasoning_detected or "",
                "their_new_risks": (critique.new_risks_identified or [])[:3],
            }
        )
    return out


def _own_prior_digest(
    own: IndependentOpinion,
    prior_critique: DebateCritique | None,
) -> dict:
    return {
        "round1_stance": own.stance,
        "round1_confidence": own.confidence,
        "round1_top_risks": (own.key_risks or [])[:3],
        "round1_reasoning_titles": [s.title for s in (own.reasoning_steps or [])[:3]],
        "prior_critique": {
            "strongest_counterargument": (
                prior_critique.strongest_counterargument if prior_critique else ""
            ),
            "weakest_reasoning_detected": (
                prior_critique.weakest_reasoning_detected if prior_critique else ""
            ),
            "new_risks_identified": (
                prior_critique.new_risks_identified if prior_critique else []
            ),
        },
    }


async def _revise_one(
    desk_key: str,
    client: BaseDeliberationClient,
    round1: dict[str, IndependentOpinion],
    prior_critique: DebateCritique | None,
    debate1: dict[str, DebateCritique],
    assignment: DebateAssignment | None,
    *,
    use_roles: bool,
) -> tuple[str, DebateCritique]:
    own = round1.get(desk_key)
    if not own or own.error:
        return desk_key, DebateCritique(
            model=client.model_key,
            role_key=desk_key,
            error="skipped — no valid round1 opinion",
        )
    old_conf = (
        prior_critique.confidence_revision.new
        if prior_critique and prior_critique.confidence_revision
        else own.confidence
    )
    system = load_prompt("revision.txt")
    if use_roles:
        role_prompt = load_role_prompt(desk_key)
        if role_prompt:
            system = f"{system}\n\n--- Your desk role during revision ---\n{role_prompt[:800]}"

    peer_critiques = _summarize_peer_critiques(desk_key, debate1)
    own_digest = _own_prior_digest(own, prior_critique)
    assignment_payload: dict = {}
    if assignment is not None:
        assignment_payload = {
            "assigned_targets": assignment.targets,
            "assigned_role": assignment.role,
            "rationale": assignment.rationale,
        }
    user = (
        "Your prior view & critique (do NOT repeat these claims verbatim):\n"
        f"{json.dumps(own_digest, indent=2)}\n\n"
        "Peer critiques that named you specifically — respond to each by desk id:\n"
        f"{json.dumps(peer_critiques, indent=2)}\n\n"
        f"Routing for this round:\n{json.dumps(assignment_payload, indent=2)}\n\n"
        f'Return JSON with "model" set to "{client.model_key}", '
        f'"role_key" set to "{desk_key}". '
        f"confidence_revision.old must be {old_conf}."
    )
    try:
        raw = await client.complete_json(system, user)
        critique = parse_strict_json(raw, DebateCritique)
        critique.model = client.model_key
        critique.role_key = critique.role_key or desk_key
        critique.role_label = critique.role_label or own.role_label
        if critique.confidence_revision and critique.confidence_revision.old != old_conf:
            critique.confidence_revision.old = old_conf
        return desk_key, critique
    except Exception as e:
        log.warning("dil.debate2.desk_failed", desk=desk_key, error=str(e))
        return desk_key, DebateCritique(
            model=client.model_key,
            role_key=desk_key,
            role_label=own.role_label,
            error=str(e),
        )


async def run_revision_round(
    desks: list[DeskDefinition],
    client_map: dict[str, BaseDeliberationClient],
    round1: dict[str, IndependentOpinion],
    debate1: dict[str, DebateCritique],
    *,
    use_routing: bool = True,
    round_index: int = 2,
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
            _revise_one(
                desk_key,
                client,
                round1,
                debate1.get(desk_key),
                debate1,
                assignment_for(assignments, desk_key),
                use_roles=use_roles or bool(global_settings.dil_use_role_specialization),
            )
        )

    results = await asyncio.gather(*tasks)
    return dict(results), assignments
