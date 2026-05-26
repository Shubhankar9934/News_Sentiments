"""Tests for desk-centric DIL configuration and provider failover."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.services.deliberation.desk_config import DeskDefinition, build_desk_registry, get_active_desks
from app.services.deliberation.role_executor import execute_desk
from app.services.deliberation.schemas import IndependentOpinion


class _FailThenOk:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, _client) -> IndependentOpinion:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("primary down")
        return IndependentOpinion(model="claude", stance="bullish", confidence=0.8)


class _FakeClient:
    def __init__(self, model_key: str) -> None:
        self.model_key = model_key


@pytest.mark.asyncio
async def test_execute_desk_failover():
    desk = DeskDefinition(
        key="macro_desk",
        label="Macro Desk",
        primary="gpt",
        fallbacks=("claude", "gemini"),
    )
    runner = _FailThenOk()
    client_map = {
        "gpt": _FakeClient("gpt"),
        "claude": _FakeClient("claude"),
    }

    provider, attempts, result, err = await execute_desk(
        desk,
        client_map,
        runner.run,
    )

    assert err is None
    assert provider == "claude"
    assert attempts == ["gpt", "claude"]
    assert result is not None
    assert result.stance == "bullish"


def test_active_desks_defaults_to_full_registry():
    settings = Settings()
    desks = get_active_desks(settings)
    # 13 original desks + Phase 4b reverse_bwb_structure_desk = 14.
    assert len(desks) == 14
    assert any(d.key == "reverse_bwb_structure_desk" for d in desks)


def test_active_desks_respects_env_subset():
    settings = Settings(dil_active_desks="macro_desk,options_desk")
    desks = get_active_desks(settings)
    assert [d.key for d in desks] == ["macro_desk", "options_desk"]


def test_desk_fallback_override_from_env():
    settings = Settings(
        DIL_EXCLUDE_MODELS="",
        dil_desk_fallbacks_raw="macro_desk=claude,gemini,deepseek,groq"
    )
    registry = build_desk_registry(settings)
    assert registry["macro_desk"].fallbacks == ("claude", "gemini", "deepseek", "groq")


def test_groq_primary_prefers_deepseek_fallback() -> None:
    settings = Settings(DIL_EXCLUDE_MODELS="")
    registry = build_desk_registry(settings)
    assert registry["options_desk"].primary == "groq"
    assert registry["options_desk"].fallbacks[0] == "deepseek"
    assert registry["event_risk_desk"].fallbacks[0] == "deepseek"
