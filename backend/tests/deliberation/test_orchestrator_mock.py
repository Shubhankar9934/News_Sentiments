"""Integration-style test with mocked LLM clients."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.services.deliberation.orchestrator import DeliberationOrchestrator
from app.services.deliberation.schemas import IndependentOpinion


def _opinion_json(model: str, stance: str, conf: float) -> str:
    return json.dumps(
        {
            "model": model,
            "stance": stance,
            "confidence": conf,
            "time_horizon": "1-3d",
            "reasoning_steps": [{"step": 1, "title": "Macro", "analysis": "test"}],
            "key_risks": ["risk a"],
            "invalidators": [],
            "position_size_suggestion": "small",
            "hidden_assumptions": [],
        }
    )


def _critique_json(model: str, old: float, new: float) -> str:
    return json.dumps(
        {
            "model": model,
            "agrees_with": [],
            "disagrees_with": ["gpt"] if model != "gpt" else ["claude"],
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
        if "Other models" not in user and "prior critique" not in user.lower():
            stance = "bullish" if self.model_key == "gpt" else "bearish"
            return _opinion_json(self.model_key, stance, 0.7 if self.model_key == "gpt" else 0.6)
        if "FINAL" in system or "revision" in system.lower():
            return _critique_json(self.model_key, 0.65, 0.62)
        return _critique_json(self.model_key, 0.7, 0.66)


@pytest.mark.asyncio
async def test_orchestrator_with_mock_clients():
    settings = Settings(
        dil_enabled=True,
        dil_min_models=2,
        openai_api_key="x",
        anthropic_api_key="y",
    )
    report = {
        "overall_sentiment_label": "Bullish",
        "_pipeline_meta": {"run_id": "test-run", "volatility_regime": "medium"},
    }
    fake_clients = [_FakeClient("gpt"), _FakeClient("claude")]

    with patch(
        "app.services.deliberation.orchestrator.get_enabled_clients",
        return_value=fake_clients,
    ):
        orch = DeliberationOrchestrator(settings)
        result = await orch.run(report, "AAPL")

    assert result.status == "complete"
    assert result.round1
    assert len(result.debate_rounds) == 2
    assert result.consensus
    assert result.metrics
