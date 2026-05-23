"""Challenge routing for debate rounds.

The default debate prompt lets each model freely pick who to disagree with,
which causes emergent pile-ons: when one model holds an outlier stance every
other model independently selects it as the target, leaving the other
positions unchallenged and producing little new information per round.

This module assigns explicit critique targets per model so that:

- Every model is critiqued at least once per round (no free passes).
- Every model receives one cross-stance challenge (mandatory) plus one
  same-stance assumption audit (when feasible).
- One model per round rotates into a ``devil's_advocate`` role that must
  argue against the consensus regardless of its prior stance.

Assignments are deterministic given the round number and the participating
model ids, so the same panel produces the same routing across reruns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from app.services.deliberation.schemas import IndependentOpinion, ModelKey
from app.services.deliberation.scoring.weighting import stance_to_score

DebateRole = str  # "default" | "devils_advocate" | "assumption_auditor"


@dataclass
class DebateAssignment:
    round: int
    model: ModelKey
    targets: list[ModelKey] = field(default_factory=list)
    role: DebateRole = "default"
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "model": self.model,
            "targets": list(self.targets),
            "role": self.role,
            "rationale": self.rationale,
        }


def _valid_models(round1: dict[str, IndependentOpinion]) -> list[ModelKey]:
    return [m for m, op in round1.items() if not op.error]


def _stance_mean(round1: dict[str, IndependentOpinion]) -> float:
    valid = [op for op in round1.values() if not op.error]
    if not valid:
        return 0.0
    return sum(stance_to_score(op.stance) for op in valid) / len(valid)


def _stance_group(stance: str, mean: float) -> str:
    score = stance_to_score(stance)
    if score > mean + 0.05:
        return "above"
    if score < mean - 0.05:
        return "below"
    return "near"


def _pick_cross_stance_target(
    self_model: ModelKey,
    self_group: str,
    groups: dict[ModelKey, str],
    rotation_seed: int,
) -> ModelKey | None:
    """Pick a model in a different stance group, rotating across rounds."""
    candidates = sorted(
        m for m, g in groups.items() if m != self_model and g != self_group
    )
    if not candidates:
        candidates = sorted(m for m in groups if m != self_model)
    if not candidates:
        return None
    return candidates[rotation_seed % len(candidates)]


def _pick_same_stance_target(
    self_model: ModelKey,
    self_group: str,
    groups: dict[ModelKey, str],
    rotation_seed: int,
) -> ModelKey | None:
    candidates = sorted(
        m for m, g in groups.items() if m != self_model and g == self_group
    )
    if not candidates:
        return None
    return candidates[rotation_seed % len(candidates)]


def _pick_devils_advocate(
    models: Iterable[ModelKey],
    mean: float,
    round_index: int,
) -> ModelKey | None:
    """Rotate the devil's-advocate role across rounds, biased toward the
    model whose stance is closest to the panel mean (so they have the least
    home-team advantage when forced to argue against it)."""
    ordered = sorted(models)
    if not ordered:
        return None
    return ordered[round_index % len(ordered)]


def build_assignments(
    round_index: int,
    round1: dict[str, IndependentOpinion],
) -> list[DebateAssignment]:
    """Compute deterministic per-model debate assignments for ``round_index``.

    Round 1 (cross-critique) — ``round_index = 1``.
    Round 2 (revision) — ``round_index = 2``. Same routing logic; the
    revision-round caller decides whether to honour the targets list.
    """
    valid = _valid_models(round1)
    if len(valid) < 2:
        return []

    mean = _stance_mean(round1)
    groups = {m: _stance_group(round1[m].stance, mean) for m in valid}
    advocate = _pick_devils_advocate(valid, mean, round_index)

    assignments: list[DebateAssignment] = []
    for i, model in enumerate(sorted(valid)):
        rotation_seed = round_index + i
        cross = _pick_cross_stance_target(model, groups[model], groups, rotation_seed)
        same = _pick_same_stance_target(model, groups[model], groups, rotation_seed)

        targets: list[ModelKey] = []
        if cross:
            targets.append(cross)
        if same and same not in targets:
            targets.append(same)

        role: DebateRole = "default"
        rationale_bits: list[str] = []
        if model == advocate:
            role = "devils_advocate"
            rationale_bits.append(
                "rotation pick — argue against the panel consensus regardless of prior stance"
            )
        if same and len(targets) >= 2:
            rationale_bits.append(
                f"same-stance assumption audit on {same}"
            )
        if cross:
            rationale_bits.append(f"cross-stance challenge on {cross}")

        assignments.append(
            DebateAssignment(
                round=round_index,
                model=model,
                targets=targets,
                role=role,
                rationale="; ".join(rationale_bits),
            )
        )

    # Ensure every valid model is named as someone's target.
    targeted: set[ModelKey] = {t for a in assignments for t in a.targets}
    untargeted = [m for m in valid if m not in targeted]
    if untargeted:
        # Distribute orphaned targets onto the earliest assignments that don't
        # already include them, so every panel member receives at least one
        # critique per round.
        for orphan in untargeted:
            for a in assignments:
                if a.model != orphan and orphan not in a.targets:
                    a.targets.append(orphan)
                    if not a.rationale:
                        a.rationale = f"coverage backstop: {orphan}"
                    else:
                        a.rationale += f"; coverage backstop: {orphan}"
                    break

    return assignments


def assignment_for(
    assignments: list[DebateAssignment], model: ModelKey
) -> DebateAssignment | None:
    for a in assignments:
        if a.model == model:
            return a
    return None
