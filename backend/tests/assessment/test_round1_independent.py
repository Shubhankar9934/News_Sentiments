"""Round 1 strict JSON validation.

The Assessment Team's Round 1 path must always emit a usable
``AssessmentMemberOpinion`` even when the underlying LLM blows up, and
must accept a real well-formed JSON payload.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.services.assessment.assessment_config import get_assessment_members
from app.services.assessment.round1_independent import run_assessment_round1
from app.services.deliberation.llm_clients.base import BaseDeliberationClient
from app.services.deliberation.schemas import (
    DeskResearchReport,
    IntelligencePackage,
)


class _FakeClient(BaseDeliberationClient):
    """Async client that returns a canned JSON blob (or raises)."""

    def __init__(self, model: str, response: str, raise_exc: bool = False) -> None:
        self.model_key = model  # type: ignore[assignment]
        self._response = response
        self._raise = raise_exc
        self.calls: list[tuple[str, str]] = []

    async def complete_json(
        self, system: str, user: str, max_tokens: int = 3000
    ) -> str:
        self.calls.append((system, user))
        if self._raise:
            raise RuntimeError("simulated provider failure")
        return self._response


def _intel(ticker: str = "SPY") -> IntelligencePackage:
    desks: dict[str, DeskResearchReport] = {
        "options_desk": DeskResearchReport(
            role_key="options_desk",
            role_label="Options Desk",
            model="gpt",
            analytical_view="neutral",
            key_findings=["IV30 quiet", "RV20 below IV by 4pts"],
            metrics={"iv30": 18.0, "rv20": 14.0},
            risks=["macro hot data"],
            invalidators=["close below body"],
            confidence_in_analysis=0.75,
        ),
    }
    return IntelligencePackage(
        ticker=ticker,
        question="Should we enter this Reverse BWB?",
        trigger="reverse_bwb",
        desks=desks,
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


def _valid_payload(model: str, role: str, label: str) -> str:
    return json.dumps(
        {
            "model": model,
            "assessment_role": role,
            "assessment_label": label,
            "credit_safety_score": 7.5,
            "risk": "Low",
            "confidence": "Medium",
            "today_outlook": "Sideways",
            "next_3d_outlook": "Sideways",
            "chance_up_2_3_pct": "Low",
            "chance_down_2_3_pct": "Low",
            "expected_range_today": {"low": 418.0, "high": 422.0},
            "expected_range_next_3d": {"low": 415.0, "high": 425.0},
            "danger_zone": "Body 418-422 — pin pressure if SPY closes inside.",
            "pin_risk": "Medium",
            "event_risk": "Low",
            "iv_quality": "Average",
            "liquidity": "Good",
            "actual_dynamics_summary": [
                "Move is bounded by the body for now.",
                "Earnings are weeks away.",
                "IV roughly tracks realised volatility.",
            ],
        }
    )


def _settings() -> Settings:
    return Settings()


@pytest.mark.asyncio
async def test_round1_parses_strict_json(monkeypatch) -> None:
    settings = _settings()
    members = get_assessment_members(settings)

    client_map = {
        m.primary: _FakeClient(
            m.primary,
            _valid_payload(m.primary, m.key, m.label),
        )
        for m in members
    }

    intel = _intel()
    round1 = await run_assessment_round1(members, client_map, intel)

    assert len(round1) == len(members)
    for member in members:
        op = round1[member.key]
        assert op.error is None
        assert op.assessment_role == member.key
        assert op.credit_safety_score == pytest.approx(7.5)
        assert op.actual_dynamics_summary[0].startswith("Move is bounded")


@pytest.mark.asyncio
async def test_round1_emits_error_opinion_when_all_providers_fail() -> None:
    settings = _settings()
    members = get_assessment_members(settings)

    # Every model fails for every member -> provider chain exhausts.
    failing: dict[str, BaseDeliberationClient] = {}
    all_models = {m.primary for m in members}
    for m in members:
        for fb in m.fallbacks:
            all_models.add(fb)
    for model in all_models:
        failing[model] = _FakeClient(model, "", raise_exc=True)

    intel = _intel()
    round1 = await run_assessment_round1(members, failing, intel)

    assert len(round1) == len(members)
    for member in members:
        op = round1[member.key]
        assert op.error  # provider exhausted
        # Even a failed opinion must satisfy the Pydantic constraints so
        # Round 2/3/4 can serialise it without blowing up.
        assert op.credit_safety_score == 0.0
        assert len(op.actual_dynamics_summary) >= 3


@pytest.mark.asyncio
async def test_round1_rejects_malformed_payload() -> None:
    settings = _settings()
    members = get_assessment_members(settings)

    # Each provider returns a payload missing required fields → should
    # be treated as a parse failure and surface an ``error`` on the
    # opinion (the round still completes for the rest of the team).
    bad_payload = json.dumps({"model": "gpt", "credit_safety_score": "n/a"})
    client_map = {
        m.primary: _FakeClient(m.primary, bad_payload) for m in members
    }
    # Provide fallbacks too so the executor exhausts them.
    for m in members:
        for fb in m.fallbacks:
            client_map.setdefault(
                fb, _FakeClient(fb, bad_payload)
            )

    intel = _intel()
    round1 = await run_assessment_round1(members, client_map, intel)
    for op in round1.values():
        assert op.error is not None
