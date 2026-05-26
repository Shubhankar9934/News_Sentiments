"""Tests for DebateCritique desk reference normalization."""

from __future__ import annotations

from app.services.deliberation.schemas import DebateCritique


def test_debate_critique_accepts_dict_desk_refs() -> None:
    critique = DebateCritique.model_validate(
        {
            "model": "gpt",
            "role_key": "devils_advocate_desk",
            "disagrees_with": [
                {"desk": "earnings_desk", "reason": "Overstates earnings resilience."},
                "macro_desk",
            ],
            "agrees_with": [{"desk_key": "risk_desk"}],
        }
    )
    assert critique.disagrees_with == ["earnings_desk", "macro_desk"]
    assert critique.agrees_with == ["risk_desk"]
