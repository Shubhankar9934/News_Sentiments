"""Tests for debate challenge routing."""

from __future__ import annotations

from app.services.deliberation.debate.routing import build_assignments
from app.services.deliberation.schemas import IndependentOpinion


def _panel():
    """Four-desk panel with one bullish outlier."""
    return {
        "macro_desk": IndependentOpinion(
            model="gpt",
            stance="mixed",
            confidence=0.60,
            role_key="macro_desk",
            role_label="Macro Desk",
        ),
        "options_desk": IndependentOpinion(
            model="groq",
            stance="bullish",
            confidence=0.65,
            role_key="options_desk",
            role_label="Options Desk",
        ),
        "fundamental_desk": IndependentOpinion(
            model="claude",
            stance="neutral",
            confidence=0.52,
            role_key="fundamental_desk",
            role_label="Fundamental Desk",
        ),
        "risk_desk": IndependentOpinion(
            model="deepseek",
            stance="mixed",
            confidence=0.55,
            role_key="risk_desk",
            role_label="Risk Desk",
        ),
    }


def test_every_desk_receives_at_least_one_critique():
    assignments = build_assignments(round_index=1, round1=_panel())
    targeted = {t for a in assignments for t in a.targets}
    assert {"macro_desk", "options_desk", "fundamental_desk", "risk_desk"}.issubset(targeted)


def test_one_devils_advocate_per_round():
    assignments = build_assignments(round_index=1, round1=_panel())
    advocates = [a for a in assignments if a.role == "debate_devils_advocate"]
    assert len(advocates) == 1


def test_devils_advocate_rotates_across_rounds():
    r1 = build_assignments(round_index=1, round1=_panel())
    r2 = build_assignments(round_index=2, round1=_panel())
    a1 = next(a.desk_key for a in r1 if a.role == "debate_devils_advocate")
    a2 = next(a.desk_key for a in r2 if a.role == "debate_devils_advocate")
    assert a1 != a2


def test_cross_stance_assignment_spreads_targets():
    assignments = build_assignments(round_index=1, round1=_panel())
    target_counts: dict[str, int] = {}
    for a in assignments:
        for t in a.targets:
            target_counts[t] = target_counts.get(t, 0) + 1
    max_count = max(target_counts.values())
    min_count = min(target_counts.values())
    assert max_count - min_count <= 2


def test_assignments_are_deterministic():
    r1a = build_assignments(round_index=1, round1=_panel())
    r1b = build_assignments(round_index=1, round1=_panel())
    assert [a.to_dict() for a in r1a] == [a.to_dict() for a in r1b]


def test_routing_handles_panel_with_errors():
    panel = _panel()
    panel["fundamental_desk"] = IndependentOpinion(
        model="claude",
        stance="neutral",
        confidence=0.0,
        error="timeout",
        role_key="fundamental_desk",
    )
    assignments = build_assignments(round_index=1, round1=panel)
    desks = {a.desk_key for a in assignments}
    assert "fundamental_desk" not in desks
    targeted = {t for a in assignments for t in a.targets}
    assert "fundamental_desk" not in targeted
