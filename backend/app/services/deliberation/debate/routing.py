"""Challenge routing for debate rounds — desk-keyed."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.deliberation.schemas import IndependentOpinion
from app.services.deliberation.scoring.weighting import stance_to_score

DebateRole = str  # "default" | "debate_devils_advocate" | "assumption_auditor"
DeskKey = str


@dataclass
class DebateAssignment:
    round: int
    desk_key: DeskKey
    targets: list[DeskKey] = field(default_factory=list)
    role: DebateRole = "default"
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "desk_key": self.desk_key,
            "targets": list(self.targets),
            "role": self.role,
            "rationale": self.rationale,
            # Legacy field for older frontends.
            "model": self.desk_key,
        }


def _valid_desks(round1: dict[str, IndependentOpinion]) -> list[DeskKey]:
    return [k for k, op in round1.items() if not op.error]


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
    self_desk: DeskKey,
    self_group: str,
    groups: dict[DeskKey, str],
    rotation_seed: int,
) -> DeskKey | None:
    candidates = sorted(
        d for d, g in groups.items() if d != self_desk and g != self_group
    )
    if not candidates:
        candidates = sorted(d for d in groups if d != self_desk)
    if not candidates:
        return None
    return candidates[rotation_seed % len(candidates)]


def _pick_same_stance_target(
    self_desk: DeskKey,
    self_group: str,
    groups: dict[DeskKey, str],
    rotation_seed: int,
) -> DeskKey | None:
    candidates = sorted(
        d for d, g in groups.items() if d != self_desk and g == self_group
    )
    if not candidates:
        return None
    return candidates[rotation_seed % len(candidates)]


def _pick_devils_advocate(
    desks: list[DeskKey],
    round_index: int,
) -> DeskKey | None:
    ordered = sorted(desks)
    if not ordered:
        return None
    return ordered[round_index % len(ordered)]


def build_assignments(
    round_index: int,
    round1: dict[str, IndependentOpinion],
) -> list[DebateAssignment]:
    valid = _valid_desks(round1)
    if len(valid) < 2:
        return []

    mean = _stance_mean(round1)
    groups = {d: _stance_group(round1[d].stance, mean) for d in valid}
    advocate = _pick_devils_advocate(valid, round_index)

    assignments: list[DebateAssignment] = []
    for i, desk in enumerate(sorted(valid)):
        rotation_seed = round_index + i
        cross = _pick_cross_stance_target(desk, groups[desk], groups, rotation_seed)
        same = _pick_same_stance_target(desk, groups[desk], groups, rotation_seed)

        targets: list[DeskKey] = []
        if cross:
            targets.append(cross)
        if same and same not in targets:
            targets.append(same)

        role: DebateRole = "default"
        rationale_bits: list[str] = []
        if desk == advocate:
            role = "debate_devils_advocate"
            rationale_bits.append(
                "rotation pick — argue against the panel consensus regardless of prior stance"
            )
        if same and len(targets) >= 2:
            rationale_bits.append(f"same-stance assumption audit on {same}")
        if cross:
            rationale_bits.append(f"cross-stance challenge on {cross}")

        assignments.append(
            DebateAssignment(
                round=round_index,
                desk_key=desk,
                targets=targets,
                role=role,
                rationale="; ".join(rationale_bits),
            )
        )

    targeted: set[DeskKey] = {t for a in assignments for t in a.targets}
    untargeted = [d for d in valid if d not in targeted]
    if untargeted:
        for orphan in untargeted:
            for a in assignments:
                if a.desk_key != orphan and orphan not in a.targets:
                    a.targets.append(orphan)
                    if not a.rationale:
                        a.rationale = f"coverage backstop: {orphan}"
                    else:
                        a.rationale += f"; coverage backstop: {orphan}"
                    break

    return assignments


def assignment_for(
    assignments: list[DebateAssignment], desk_key: DeskKey
) -> DebateAssignment | None:
    for a in assignments:
        if a.desk_key == desk_key:
            return a
    return None
