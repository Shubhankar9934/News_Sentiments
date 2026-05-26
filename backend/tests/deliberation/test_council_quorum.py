"""Council quorum and degraded consensus tests."""

from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.services.deliberation.council import run_decision_council
from app.services.deliberation.llm_clients.base import BaseDeliberationClient
from app.services.deliberation.schemas import (
    DeskResearchReport,
    IntelligencePackage,
)
from app.services.dil_resilience.registry import reset_resilience_registry


def _intel() -> IntelligencePackage:
    return IntelligencePackage(
        ticker="SPY",
        question="Should we enter this Reverse BWB?",
        trigger="reverse_bwb",
        desks={
            "options_desk": DeskResearchReport(
                role_key="options_desk",
                role_label="Options Desk",
                model="gpt",
                analytical_view="neutral",
                confidence_in_analysis=0.7,
            ),
        },
        options_snapshot={"spot": 420.0},
        credit_safety={"score": 7.0},
    )


def _decision_payload(model: str, role: str, label: str, decision: str) -> str:
    return json.dumps(
        {
            "model": model,
            "council_role": role,
            "council_label": label,
            "decision": decision,
            "confidence": 0.7,
            "reasoning_steps": [
                {"step": 1, "title": "A", "analysis": "x"},
                {"step": 2, "title": "B", "analysis": "y"},
                {"step": 3, "title": "C", "analysis": "z"},
                {"step": 4, "title": "D", "analysis": "w"},
                {"step": 5, "title": "E", "analysis": "v"},
            ],
            "key_risks": ["risk"],
        }
    )


def _critique_payload(model: str, role: str, label: str) -> str:
    return json.dumps(
        {
            "model": model,
            "council_role": role,
            "council_label": label,
            "agrees_with": [],
            "disagrees_with": [],
            "strongest_counterargument": "",
            "weakest_reasoning_detected": "",
            "new_risks_identified": [],
        }
    )


def _revision_payload(model: str, role: str, label: str, decision: str) -> str:
    return json.dumps(
        {
            "model": model,
            "council_role": role,
            "council_label": label,
            "prior_decision": decision,
            "revised_decision": decision,
            "prior_confidence": 0.7,
            "revised_confidence": 0.75,
            "revision_rationale": "unchanged",
        }
    )


class _ScriptedClient(BaseDeliberationClient):
    def __init__(self, model: str, responses: list[str]) -> None:
        super().__init__(Settings())
        self.model_key = model  # type: ignore[assignment]
        self._responses = list(responses)

    async def complete_json(
        self, system: str, user: str, max_tokens: int = 3000
    ) -> str:
        if not self._responses:
            raise RuntimeError("out of responses")
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_resilience_registry()


@pytest.mark.asyncio
async def test_council_degraded_quorum_3_of_5() -> None:
    settings = Settings(DIL_COUNCIL_MIN_MEMBERS=3)
    roles = [
        ("gpt", "portfolio_manager", "Portfolio Manager", "ENTER"),
        ("claude", "risk_manager", "Risk Manager", "ENTER"),
        ("deepseek", "quant_reviewer", "Quant Reviewer", "WAIT"),
    ]
    client_map: dict[str, BaseDeliberationClient] = {}
    for model, role, label, decision in roles:
        client_map[model] = _ScriptedClient(
            model,
            [
                _decision_payload(model, role, label, decision),
                _critique_payload(model, role, label),
                _revision_payload(model, role, label, decision),
            ],
        )
    # gemini and groq fail
    client_map["gemini"] = _ScriptedClient("gemini", [])
    client_map["groq"] = _ScriptedClient("groq", [])

    layer = await run_decision_council(_intel(), client_map, settings)
    assert layer is not None
    assert layer.degraded is True
    assert layer.quorum_meta["valid"] == 3
    assert layer.consensus is not None
    assert "Partial council" in layer.consensus.main_conflict


@pytest.mark.asyncio
async def test_council_below_quorum_returns_none() -> None:
    settings = Settings(DIL_COUNCIL_MIN_MEMBERS=3)
    failing = {m: _ScriptedClient(m, []) for m in ("gpt", "claude", "deepseek", "gemini", "groq")}
    layer = await run_decision_council(_intel(), failing, settings)
    assert layer is None
