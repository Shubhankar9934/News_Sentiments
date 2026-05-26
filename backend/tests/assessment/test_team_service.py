"""End-to-end smoke test for the Assessment Team service.

Wires three fake LLM clients into ``run_assessment_team`` and asserts:

* Round 1 / Round 2 / Round 3 each populate per-member entries.
* Round 4 deterministic consensus is non-null and matches the median
  / modal aggregation of the canned payloads.
* The returned ``AssessmentLayer`` carries the consensus + meta.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.config import Settings
from app.services.assessment.team_service import run_assessment_team
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
                key_findings=["IV30 quiet", "RV20 below IV"],
                metrics={"iv30": 18.0, "rv20": 14.0},
                risks=["macro surprise"],
                invalidators=["body break"],
                confidence_in_analysis=0.75,
            ),
        },
        options_snapshot={
            "spot": 420.0,
            "body": {"low": 415.0, "high": 425.0},
            "iv30": 18.0,
            "rv20": 14.0,
        },
        credit_safety={
            "label": "SAFE",
            "score": 7.2,
            "expected_range": {"low": 415.0, "high": 425.0},
        },
    )


def _opinion_payload(model: str, role: str, label: str, *, score: float, risk: str) -> str:
    return json.dumps(
        {
            "model": model,
            "assessment_role": role,
            "assessment_label": label,
            "credit_safety_score": score,
            "risk": risk,
            "confidence": "Medium",
            "today_outlook": "Sideways",
            "next_3d_outlook": "Sideways",
            "chance_up_2_3_pct": "Low",
            "chance_down_2_3_pct": "Low",
            "expected_range_today": {"low": 418.0, "high": 422.0},
            "expected_range_next_3d": {"low": 415.0, "high": 425.0},
            "danger_zone": "Body 418-422 — pin pressure risk.",
            "pin_risk": "Medium",
            "event_risk": "Low",
            "iv_quality": "Average",
            "liquidity": "Good",
            "actual_dynamics_summary": [
                f"{label} read: move is bounded by the body.",
                "Earnings far enough away.",
                "IV roughly matches realised volatility.",
            ],
        }
    )


def _critique_payload(model: str, role: str, label: str) -> str:
    return json.dumps(
        {
            "model": model,
            "assessment_role": role,
            "assessment_label": label,
            "agrees_with": [],
            "disagrees_with": [],
            "numeric_disagreements": [],
            "enum_disagreements": [],
            "missed_risks": [],
            "summary": "Broad agreement on the body cushion.",
        }
    )


def _revision_payload(
    model: str, role: str, label: str, *, score: float, risk: str
) -> str:
    revised = json.loads(_opinion_payload(model, role, label, score=score, risk=risk))
    return json.dumps(
        {
            "model": model,
            "assessment_role": role,
            "assessment_label": label,
            "revised_opinion": revised,
            "revision_rationale": "Nudged numeric slightly after peer critique.",
        }
    )


class _ScriptedClient(BaseDeliberationClient):
    """Returns a different canned blob on each call, in declaration order."""

    def __init__(self, model: str, responses: list[str]) -> None:
        super().__init__(Settings())
        self.model_key = model  # type: ignore[assignment]
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def complete_json(
        self, system: str, user: str, max_tokens: int = 3000
    ) -> str:
        self.calls.append((system, user))
        if not self._responses:
            raise RuntimeError("scripted client out of canned responses")
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def _reset_resilience() -> None:
    reset_resilience_registry()


@pytest.mark.asyncio
async def test_run_assessment_team_emits_consensus_layer() -> None:
    settings = Settings()

    canned_scores: dict[str, tuple[float, str]] = {
        "gpt": (8.0, "Low"),
        "claude": (7.0, "Medium"),
        "deepseek": (6.0, "High"),
    }
    canned_labels: dict[str, tuple[str, str]] = {
        "gpt": (
            "openai_assessment_analyst",
            "OpenAI Assessment Analyst",
        ),
        "claude": (
            "claude_risk_assessment_analyst",
            "Claude Risk Assessment Analyst",
        ),
        "deepseek": (
            "deepseek_quant_assessment_analyst",
            "DeepSeek Quant Assessment Analyst",
        ),
    }

    client_map: dict[str, BaseDeliberationClient] = {}
    for model, (role, label) in canned_labels.items():
        score, risk = canned_scores[model]
        client_map[model] = _ScriptedClient(
            model,
            [
                _opinion_payload(model, role, label, score=score, risk=risk),
                _critique_payload(model, role, label),
                _revision_payload(model, role, label, score=score, risk=risk),
            ],
        )

    layer = await run_assessment_team(_intel(), client_map, settings)

    assert layer is not None
    assert layer.consensus is not None
    # Median of 8.0 / 7.0 / 6.0 -> 7.0.
    assert layer.consensus.credit_safety_score == pytest.approx(7.0)
    assert len(layer.round1) == 3
    assert len(layer.round2) == 3
    assert len(layer.round3) == 3
    assert layer.consensus_meta["members_valid"] == 3


@pytest.mark.asyncio
async def test_run_assessment_team_returns_none_below_quorum() -> None:
    settings = Settings()
    # All three primary providers fail → no usable member opinions.
    failing_clients: dict[str, BaseDeliberationClient] = {
        "gpt": _ScriptedClient("gpt", []),
        "claude": _ScriptedClient("claude", []),
        "deepseek": _ScriptedClient("deepseek", []),
    }
    layer = await run_assessment_team(_intel(), failing_clients, settings)
    assert layer is None


@pytest.mark.asyncio
async def test_run_assessment_team_degraded_when_one_member_fails() -> None:
    settings = Settings(DIL_ASSESSMENT_MIN_MEMBERS=2)
    canned_labels = {
        "gpt": ("openai_assessment_analyst", "OpenAI Assessment Analyst"),
        "claude": ("claude_risk_assessment_analyst", "Claude Risk Assessment Analyst"),
    }
    client_map: dict[str, BaseDeliberationClient] = {}
    for model, (role, label) in canned_labels.items():
        client_map[model] = _ScriptedClient(
            model,
            [
                _opinion_payload(model, role, label, score=7.0, risk="Low"),
                _critique_payload(model, role, label),
                _revision_payload(model, role, label, score=7.0, risk="Low"),
            ],
        )
    client_map["deepseek"] = _ScriptedClient("deepseek", [])

    layer = await run_assessment_team(_intel(), client_map, settings)
    assert layer is not None
    assert layer.degraded is True
    assert layer.quorum_meta["valid"] == 2
    assert layer.consensus is not None
