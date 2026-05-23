"""Debate round 2: final revision.

PR3 changes:
- Inject *peer* critiques targeted at this model into the context, not just
  the model's own prior critique. Without this the LLM has no new
  information to react to and tends to restate Round 1 verbatim.
- Honour challenge-routing assignments from PR2 if provided.
- Provide structured anti-repetition cues in the user payload so the prompt
  can ask the model not to recycle prior text.
"""

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


def _summarize_peer_critiques(
    self_model: ModelKey,
    debate1: dict[str, DebateCritique],
) -> list[dict]:
    """Return the critiques from other models that named ``self_model`` as a
    target of either agreement or disagreement, plus their headline claims.
    The revision model is expected to respond to each of these by id.
    """
    out: list[dict] = []
    for other, critique in debate1.items():
        if other == self_model or critique.error:
            continue
        agreed = self_model in (critique.agrees_with or [])
        disagreed = self_model in (critique.disagrees_with or [])
        if not agreed and not disagreed:
            continue
        out.append(
            {
                "from": other,
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
    """Compact structured delta of what the model already said.

    Used both for revision context and as an "avoid repeating these" hint —
    the prompt instructs the model not to recycle these exact claims.
    """
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
    client: BaseDeliberationClient,
    round1: dict[str, IndependentOpinion],
    prior_critique: DebateCritique | None,
    debate1: dict[str, DebateCritique],
    assignment: DebateAssignment | None,
) -> tuple[ModelKey, DebateCritique]:
    own = round1.get(client.model_key)
    if not own or own.error:
        return client.model_key, DebateCritique(
            model=client.model_key,
            error="skipped — no valid round1 opinion",
        )
    old_conf = (
        prior_critique.confidence_revision.new
        if prior_critique and prior_critique.confidence_revision
        else own.confidence
    )
    system = load_prompt("revision.txt")
    peer_critiques = _summarize_peer_critiques(client.model_key, debate1)
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
        "Peer critiques that named you specifically — respond to each by id:\n"
        f"{json.dumps(peer_critiques, indent=2)}\n\n"
        f"Routing for this round:\n{json.dumps(assignment_payload, indent=2)}\n\n"
        f'Return JSON with "model" set to "{client.model_key}". '
        f"confidence_revision.old must be {old_conf}."
    )
    try:
        raw = await client.complete_json(system, user)
        critique = parse_strict_json(raw, DebateCritique)
        critique.model = client.model_key
        if critique.confidence_revision and critique.confidence_revision.old != old_conf:
            critique.confidence_revision.old = old_conf
        return client.model_key, critique
    except Exception as e:
        log.warning("dil.debate2.model_failed", model=client.model_key, error=str(e))
        return client.model_key, DebateCritique(model=client.model_key, error=str(e))


async def run_revision_round(
    clients: list[BaseDeliberationClient],
    round1: dict[str, IndependentOpinion],
    debate1: dict[str, DebateCritique],
    *,
    use_routing: bool = True,
    round_index: int = 2,
) -> tuple[dict[str, DebateCritique], list[DebateAssignment]]:
    assignments: list[DebateAssignment] = []
    if use_routing:
        assignments = build_assignments(round_index, round1)
    results = await asyncio.gather(
        *[
            _revise_one(
                c,
                round1,
                debate1.get(c.model_key),
                debate1,
                assignment_for(assignments, c.model_key),
            )
            for c in clients
        ]
    )
    return dict(results), assignments
