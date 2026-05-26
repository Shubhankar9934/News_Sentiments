"""Global LLM concurrency control."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)

WAIT_LOG_THRESHOLD_MS = 100


@dataclass
class ConcurrencyStats:
    max_concurrent: int
    active: int
    waiting: int


class LlmConcurrencyManager:
    """Process-wide semaphore limiting in-flight LLM HTTP requests."""

    def __init__(self, max_concurrent: int) -> None:
        self._max = max(1, max_concurrent)
        self._semaphore = asyncio.Semaphore(self._max)
        self._active = 0
        self._waiting = 0
        self._lock = asyncio.Lock()

    @property
    def stats(self) -> ConcurrencyStats:
        return ConcurrencyStats(
            max_concurrent=self._max,
            active=self._active,
            waiting=self._waiting,
        )

    async def acquire(self, provider: str, role: str) -> None:
        async with self._lock:
            self._waiting += 1
        wait_start = time.monotonic()
        await self._semaphore.acquire()
        wait_ms = int((time.monotonic() - wait_start) * 1000)
        async with self._lock:
            self._waiting = max(0, self._waiting - 1)
            self._active += 1
            active = self._active
            waiting = self._waiting
        if wait_ms >= WAIT_LOG_THRESHOLD_MS:
            log.info(
                "dil.resilience.concurrency.wait",
                provider=provider,
                role=role or None,
                wait_ms=wait_ms,
                active=active,
                waiting=waiting,
            )
        log.debug(
            "dil.resilience.concurrency.acquire",
            provider=provider,
            role=role or None,
            active=active,
            waiting=waiting,
        )

    async def release(self) -> None:
        async with self._lock:
            self._active = max(0, self._active - 1)
        self._semaphore.release()
