"""Tests for the new Reverse BWB Structure Desk (Phase 4b)."""

from __future__ import annotations

from pathlib import Path

from app.services.deliberation.desk_config import (
    ALL_DESK_KEYS,
    DESK_LABELS,
    ROLE_STEP_TITLES,
    context_view_for_role,
)


def test_new_desk_registered_in_all_keys():
    assert "reverse_bwb_structure_desk" in ALL_DESK_KEYS


def test_new_desk_has_label_and_step_titles():
    assert DESK_LABELS["reverse_bwb_structure_desk"] == "Reverse BWB Structure Desk"
    titles = ROLE_STEP_TITLES["reverse_bwb_structure_desk"]
    assert "Body Placement" in titles
    assert "Wing Width Adequacy" in titles
    assert "Probability of Touch" in titles


def test_new_desk_prompt_exists():
    prompt = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "deliberation"
        / "prompts"
        / "roles"
        / "reverse_bwb_structure_desk.txt"
    )
    text = prompt.read_text(encoding="utf-8")
    assert "Reverse BWB Structure Desk" in text
    assert "structure_geometry" in text
    assert "position_risk" in text


def test_context_view_for_structure_desk_focuses_on_geometry():
    context = {
        "options_intelligence": {
            "structure_geometry": {"spot": 100.0, "body_strike": 100.0},
            "position_risk": {"probability_of_touch": 0.4},
            "body_danger": {"label": "Medium"},
            "pin_risk": {"score": 0.3, "label": "Medium"},
            "reverse_bwb": {"score": 5.0},
            "move_probabilities": {"p_in_range_1sigma": 0.65},
            "expected_range": {"sigma_pct": 2.0},
            "credit_safety": {"score": 5.0, "label": "CAUTION"},
        }
    }
    view = context_view_for_role(context, "reverse_bwb_structure_desk")
    focus = view["role_focus"]
    assert focus["structure_geometry"]["spot"] == 100.0
    assert focus["position_risk"]["probability_of_touch"] == 0.4
    assert focus["body_danger"]["label"] == "Medium"
    assert focus["credit_safety"]["score"] == 5.0
