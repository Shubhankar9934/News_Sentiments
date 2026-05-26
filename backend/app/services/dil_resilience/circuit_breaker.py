"""Per-provider circuit breakers integrated with health manager."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from app.services.dil_resilience.health import ProviderHealthManager, ProviderState


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerSnapshot:
    provider: str
    state: CircuitState
    opened_at: datetime | None = None
    last_probe_at: datetime | None = None
    failure_count: int = 0
    open_count: int = 0
    half_open_probes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state.value,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "last_probe_at": (
                self.last_probe_at.isoformat() if self.last_probe_at else None
            ),
            "failure_count": self.failure_count,
            "open_count": self.open_count,
            "half_open_probes": self.half_open_probes,
        }


@dataclass
class _BreakerRecord:
    state: CircuitState = CircuitState.CLOSED
    opened_at: datetime | None = None
    last_probe_at: datetime | None = None
    failure_count: int = 0
    open_count: int = 0
    half_open_probes: int = 0


class CircuitBreaker:
    def __init__(
        self,
        provider: str,
        *,
        open_duration_s: int = 300,
        probe_interval_s: int = 30,
        failure_threshold: int = 5,
    ) -> None:
        self.provider = provider
        self.open_duration_s = open_duration_s
        self.probe_interval_s = probe_interval_s
        self.failure_threshold = failure_threshold
        self._rec = _BreakerRecord()
        self._lock = threading.Lock()

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _maybe_transition_to_half_open(self) -> None:
        if self._rec.state != CircuitState.OPEN or not self._rec.opened_at:
            return
        if self._now() >= self._rec.opened_at + timedelta(seconds=self.open_duration_s):
            self._rec.state = CircuitState.HALF_OPEN

    def allow_request(self) -> bool:
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._rec.state == CircuitState.CLOSED:
                return True
            if self._rec.state == CircuitState.OPEN:
                return False
            # HALF_OPEN — one probe per interval
            now = self._now()
            if self._rec.last_probe_at is None:
                self._rec.last_probe_at = now
                self._rec.half_open_probes += 1
                return True
            if now >= self._rec.last_probe_at + timedelta(seconds=self.probe_interval_s):
                self._rec.last_probe_at = now
                self._rec.half_open_probes += 1
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._rec.state = CircuitState.CLOSED
            self._rec.failure_count = 0
            self._rec.opened_at = None
            self._rec.last_probe_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._rec.failure_count += 1
            if self._rec.state == CircuitState.HALF_OPEN:
                self._open()
                return
            if (
                self._rec.state == CircuitState.CLOSED
                and self._rec.failure_count >= self.failure_threshold
            ):
                self._open()

    def force_open(self) -> None:
        with self._lock:
            self._open()

    def _open(self) -> None:
        self._rec.state = CircuitState.OPEN
        self._rec.opened_at = self._now()
        self._rec.open_count += 1

    def snapshot(self) -> CircuitBreakerSnapshot:
        with self._lock:
            self._maybe_transition_to_half_open()
            return CircuitBreakerSnapshot(
                provider=self.provider,
                state=self._rec.state,
                opened_at=self._rec.opened_at,
                last_probe_at=self._rec.last_probe_at,
                failure_count=self._rec.failure_count,
                open_count=self._rec.open_count,
                half_open_probes=self._rec.half_open_probes,
            )


class CircuitBreakerRegistry:
    def __init__(
        self,
        health: ProviderHealthManager,
        *,
        open_duration_s: int = 300,
        probe_interval_s: int = 30,
        failure_threshold: int = 5,
    ) -> None:
        self._health = health
        self._open_duration_s = open_duration_s
        self._probe_interval_s = probe_interval_s
        self._failure_threshold = failure_threshold
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def _get(self, provider: str) -> CircuitBreaker:
        with self._lock:
            if provider not in self._breakers:
                self._breakers[provider] = CircuitBreaker(
                    provider,
                    open_duration_s=self._open_duration_s,
                    probe_interval_s=self._probe_interval_s,
                    failure_threshold=self._failure_threshold,
                )
            return self._breakers[provider]

    def allow(self, provider: str) -> bool:
        breaker = self._get(provider)
        health_snap = self._health.snapshot(provider)
        if health_snap.state == ProviderState.COOLDOWN:
            breaker.force_open()
            return False
        if health_snap.state == ProviderState.UNHEALTHY:
            breaker.force_open()
        return breaker.allow_request()

    def record_success(self, provider: str) -> None:
        self._get(provider).record_success()

    def record_failure(self, provider: str) -> None:
        self._get(provider).record_failure()

    def filter_chain(
        self,
        chain: tuple[str, ...] | list[str],
        *,
        last_resort: bool = True,
    ) -> list[str]:
        available = [p for p in chain if self.allow(p)]
        if available:
            return available
        if last_resort:
            return list(chain)
        return []

    def all_snapshots(self) -> dict[str, CircuitBreakerSnapshot]:
        with self._lock:
            return {p: b.snapshot() for p, b in self._breakers.items()}

    def snapshot(self, provider: str) -> CircuitBreakerSnapshot:
        return self._get(provider).snapshot()
