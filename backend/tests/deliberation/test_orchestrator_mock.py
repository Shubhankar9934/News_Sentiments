"""Integration-style test with mocked LLM clients."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.services.deliberation.desk_config import DeskDefinition
from app.services.deliberation.orchestrator import DeliberationOrchestrator


def _desk_report_json(
    model: str,
    view: str,
    conf: float,
    role_key: str,
    role_label: str,
) -> str:
    return json.dumps(
        {
            "model": model,
            "role_key": role_key,
            "role_label": role_label,
            "key_findings": ["finding a"],
            "metrics": {},
            "risks": ["risk a"],
            "invalidators": [],
            "analytical_view": view,
            "confidence_in_analysis": conf,
            "reasoning_steps": [{"step": 1, "title": "Macro", "analysis": "test"}],
        }
    )


def _critique_json(model: str, role_key: str, old: float, new: float, target: str) -> str:
    return json.dumps(
        {
            "model": model,
            "role_key": role_key,
            "agrees_with": [],
            "disagrees_with": [target] if role_key != target else ["fundamental_desk"],
            "strongest_counterargument": "counter",
            "weakest_reasoning_detected": "weak",
            "new_risks_identified": ["new risk"],
            "confidence_revision": {"old": old, "new": new},
        }
    )


class _FakeClient:
    def __init__(self, model_key: str) -> None:
        self.model_key = model_key

    async def complete_json(self, system: str, user: str, max_tokens: int = 3000) -> str:
        if "Other desks" not in user and "Peer critiques" not in user:
            if "macro_desk" in user or "Macro Desk" in user:
                return _desk_report_json(
                    "gpt", "bullish", 0.7, "macro_desk", "Macro Desk"
                )
            return _desk_report_json(
                "claude", "bearish", 0.6, "fundamental_desk", "Fundamental Desk"
            )
        if "FINAL" in system or "revision" in system.lower():
            rk = "macro_desk" if self.model_key == "gpt" else "fundamental_desk"
            return _critique_json(self.model_key, rk, 0.65, 0.62, "fundamental_desk")
        rk = "macro_desk" if self.model_key == "gpt" else "fundamental_desk"
        target = "fundamental_desk" if rk == "macro_desk" else "macro_desk"
        return _critique_json(self.model_key, rk, 0.7, 0.66, target)


@pytest.mark.asyncio
async def test_orchestrator_with_mock_clients():
    settings = Settings(
        dil_enabled=True,
        dil_min_models=2,
        dil_active_desks="macro_desk,fundamental_desk",
        dil_council_enabled=False,
        dil_desk_debate_enabled=True,
        openai_api_key="x",
        anthropic_api_key="y",
    )
    report = {
        "overall_sentiment_label": "Bullish",
        "_pipeline_meta": {"run_id": "test-run", "volatility_regime": "medium"},
    }
    fake_clients = {"gpt": _FakeClient("gpt"), "claude": _FakeClient("claude")}
    fake_desks = [
        DeskDefinition(key="macro_desk", label="Macro Desk", primary="gpt", fallbacks=("claude",)),
        DeskDefinition(
            key="fundamental_desk",
            label="Fundamental Desk",
            primary="claude",
            fallbacks=("gpt",),
        ),
    ]

    with (
        patch(
            "app.services.deliberation.orchestrator.get_client_map",
            return_value=fake_clients,
        ),
        patch(
            "app.services.deliberation.orchestrator.get_active_desks",
            return_value=fake_desks,
        ),
    ):
        orch = DeliberationOrchestrator(settings)
        result = await orch.run(report, "AAPL")

    assert result.status == "complete"
    assert result.round1
    assert "macro_desk" in result.round1
    assert result.analysis_layer
    assert result.analysis_layer.get("desks")
    assert len(result.debate_rounds) == 2
    assert result.consensus
    assert result.metrics
    assert result.desks_used
