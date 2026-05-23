"""Tests for debate challenge routing."""

from __future__ import annotations

from app.services.deliberation.debate.routing import build_assignments
from app.services.deliberation.schemas import IndependentOpinion


def _panel():
    """Failing example panel: 1 bullish outlier + 2 mixed + 1 neutral."""
    return {
        "gpt": IndependentOpinion(model="gpt", stance="mixed", confidence=0.60),
        "groq": IndependentOpinion(model="groq", stance="bullish", confidence=0.65),
        "claude": IndependentOpinion(model="claude", stance="neutral", confidence=0.52),
        "deepseek": IndependentOpinion(model="deepseek", stance="mixed", confidence=0.55),
    }


def test_every_model_receives_at_least_one_critique():
    assignments = build_assignments(round_index=1, round1=_panel())
    targeted = {t for a in assignments for t in a.targets}
    # All four models must appear as someone's target — no free passes.
    assert {"gpt", "groq", "claude", "deepseek"}.issubset(targeted)


def test_one_devils_advocate_per_round():
    assignments = build_assignments(round_index=1, round1=_panel())
    advocates = [a for a in assignments if a.role == "devils_advocate"]
    assert len(advocates) == 1


def test_devils_advocate_rotates_across_rounds():
    r1 = build_assignments(round_index=1, round1=_panel())
    r2 = build_assignments(round_index=2, round1=_panel())
    a1 = next(a.model for a in r1 if a.role == "devils_advocate")
    a2 = next(a.model for a in r2 if a.role == "devils_advocate")
    assert a1 != a2


def test_cross_stance_assignment_for_outlier_avoids_pile_on():
    """Groq is the only bullish stance. In the buggy default behaviour every
    other model targets Groq. Routing should distribute targets so Groq is
    challenged but not the only one being critiqued."""
    assignments = build_assignments(round_index=1, round1=_panel())
    target_counts: dict[str, int] = {}
    for a in assignments:
        for t in a.targets:
            target_counts[t] = target_counts.get(t, 0) + 1
    max_count = max(target_counts.values())
    min_count = min(target_counts.values())
    # No model can be targeted more than 2x as often as the least-targeted —
    # spread is enforced, even when a clear outlier exists.
    assert max_count - min_count <= 2


def test_assignments_are_deterministic():
    r1a = build_assignments(round_index=1, round1=_panel())
    r1b = build_assignments(round_index=1, round1=_panel())
    assert [a.to_dict() for a in r1a] == [a.to_dict() for a in r1b]


def test_routing_handles_panel_with_errors():
    panel = _panel()
    panel["claude"] = IndependentOpinion(
        model="claude", stance="neutral", confidence=0.0, error="timeout"
    )
    assignments = build_assignments(round_index=1, round1=panel)
    models = {a.model for a in assignments}
    assert "claude" not in models  # errored model gets no assignment
    targeted = {t for a in assignments for t in a.targets}
    assert "claude" not in targeted
