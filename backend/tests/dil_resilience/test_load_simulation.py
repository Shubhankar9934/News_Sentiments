"""Load simulation tests for DIL resilience (mocked, no real API calls)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.services.dil_resilience.registry import reset_resilience_registry
from app.services.dil_resilience.executor import execute_with_failover
from app.services.deliberation.desk_config import DeskDefinition
from app.services.deliberation.llm_clients.base import BaseDeliberationClient
from app.services.deliberation.role_executor import execute_desk


class _FakeClient(BaseDeliberationClient):
    def __init__(self, model_key: str) -> None:
        super().__init__(Settings())
        self.model_key = model_key  # type: ignore[assignment]
        self.calls = 0

    async def complete_json(self, system: str, user: str, max_tokens: int = 3000) -> str:
        self.calls += 1
        return '{"ok": true}'


class _Fail429ThenOkClient(BaseDeliberationClient):
    def __init__(self, model_key: str) -> None:
        super().__init__(Settings())
        self.model_key = model_key  # type: ignore[assignment]
        self.attempts = 0

    async def complete_json(self, system: str, user: str, max_tokens: int = 3000) -> str:
        self.attempts += 1
        if self.attempts == 1:
            from app.services.dil_resilience.retry import RateLimitError

            raise RateLimitError(self.model_key, 429, "rate limited")
        return '{"ok": true}'


@pytest.fixture(autouse=True)
def _reset_gateway() -> None:
    reset_resilience_registry(
        Settings(
            DIL_RESILIENCE_ENABLED=True,
            DIL_MAX_CONCURRENT_LLM_REQUESTS=3,
        )
    )


@pytest.mark.asyncio
async def test_scenario_a_groq_failover_to_gpt() -> None:
    desk = DeskDefinition(
        key="event_risk_desk",
        label="Event Risk",
        primary="groq",
        fallbacks=("gpt",),
    )
    groq = _Fail429ThenOkClient("groq")
    gpt = _FakeClient("gpt")
    client_map = {"groq": groq, "gpt": gpt}

    async def _prompt(client: BaseDeliberationClient) -> dict[str, Any]:
        raw = await client.complete_json("", "")
        return {"raw": raw}

    provider, attempts, result, err = await execute_desk(desk, client_map, _prompt)
    assert err is None
    assert provider == "gpt"
    assert attempts == ["groq", "gpt"]


@pytest.mark.asyncio
async def test_scenario_c_concurrency_cap_respected() -> None:
    gateway = reset_resilience_registry(
        Settings(DIL_RESILIENCE_ENABLED=True, DIL_MAX_CONCURRENT_LLM_REQUESTS=2)
    )
    peak = [0]

    async def task() -> None:
        await gateway.before_request("gpt")
        peak[0] = max(peak[0], gateway.concurrency.stats.active)
        await asyncio.sleep(0.05)
        await gateway.after_request("gpt", success=True, latency_ms=50)

    await asyncio.gather(*[task() for _ in range(8)])
    assert peak[0] <= 2
