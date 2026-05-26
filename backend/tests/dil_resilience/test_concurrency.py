"""Tests for global LLM concurrency control."""

from __future__ import annotations

import asyncio

import pytest

from app.services.dil_resilience.concurrency import LlmConcurrencyManager


@pytest.mark.asyncio
async def test_semaphore_limits_in_flight() -> None:
    mgr = LlmConcurrencyManager(max_concurrent=2)
    in_flight: list[int] = []
    peak: list[int] = [0]

    async def worker() -> None:
        await mgr.acquire("gpt", "desk:macro_desk")
        async with asyncio.Lock():
            in_flight.append(1)
            peak[0] = max(peak[0], len(in_flight))
            await asyncio.sleep(0.05)
            in_flight.pop()
        await mgr.release()

    await asyncio.gather(*[worker() for _ in range(6)])
    assert peak[0] <= 2
    assert mgr.stats.active == 0
