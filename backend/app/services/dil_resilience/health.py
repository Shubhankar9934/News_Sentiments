"""Provider health tracking with in-memory store (Redis-compatible interface)."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any


class ProviderState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    COOLDOWN = "cooldown"


@dataclass
class ProviderHealthSnapshot:
    provider: str
    state: ProviderState
    success_count: int = 0
    failure_count: int = 0
    rate_limit_count: int = 0
    consecutive_failures: int = 0
    consecutive_429s: int = 0
    last_failure_at: datetime | None = None
    cooldown_until: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state.value,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "rate_limit_count": self.rate_limit_count,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_429s": self.consecutive_429s,
            "last_failure_at": (
                self.last_failure_at.isoformat() if self.last_failure_at else None
            ),
            "cooldown_until": (
                self.cooldown_until.isoformat() if self.cooldown_until else None
            ),
            "success_rate": self.success_rate,
        }

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return round(self.success_count / total, 4)


@dataclass
class _ProviderRecord:
    state: ProviderState = ProviderState.HEALTHY
    success_count: int = 0
    failure_count: int = 0
    rate_limit_count: int = 0
    consecutive_failures: int = 0
    consecutive_429s: int = 0
    last_failure_at: datetime | None = None
    cooldown_until: datetime | None = None


class HealthStore(ABC):
    """Abstract health store — swap for Redis in multi-worker deployments."""

    @abstractmethod
    def get(self, provider: str) -> ProviderHealthSnapshot: ...

    @abstractmethod
    def record_success(self, provider: str) -> ProviderHealthSnapshot: ...

    @abstractmethod
    def record_failure(
        self, provider: str, *, is_rate_limit: bool = False
    ) -> ProviderHealthSnapshot: ...

    @abstractmethod
    def all_snapshots(self) -> dict[str, ProviderHealthSnapshot]: ...


class InMemoryHealthStore(HealthStore):
    def __init__(
        self,
        *,
        degraded_429_threshold: int = 3,
        unhealthy_failure_threshold: int = 5,
        cooldown_s: int = 300,
    ) -> None:
        self.degraded_429_threshold = degraded_429_threshold
        self.unhealthy_failure_threshold = unhealthy_failure_threshold
        self.cooldown_s = cooldown_s
        self._records: dict[str, _ProviderRecord] = {}
        self._lock = threading.Lock()

    def _get_record(self, provider: str) -> _ProviderRecord:
        if provider not in self._records:
            self._records[provider] = _ProviderRecord()
        return self._records[provider]

    def _maybe_exit_cooldown(self, rec: _ProviderRecord, now: datetime) -> None:
        if rec.state == ProviderState.COOLDOWN and rec.cooldown_until:
            if now >= rec.cooldown_until:
                rec.state = ProviderState.HEALTHY
                rec.cooldown_until = None
                rec.consecutive_failures = 0
                rec.consecutive_429s = 0

    def _to_snapshot(self, provider: str, rec: _ProviderRecord) -> ProviderHealthSnapshot:
        return ProviderHealthSnapshot(
            provider=provider,
            state=rec.state,
            success_count=rec.success_count,
            failure_count=rec.failure_count,
            rate_limit_count=rec.rate_limit_count,
            consecutive_failures=rec.consecutive_failures,
            consecutive_429s=rec.consecutive_429s,
            last_failure_at=rec.last_failure_at,
            cooldown_until=rec.cooldown_until,
        )

    def get(self, provider: str) -> ProviderHealthSnapshot:
        with self._lock:
            rec = self._get_record(provider)
            self._maybe_exit_cooldown(rec, datetime.now(UTC))
            return self._to_snapshot(provider, rec)

    def record_success(self, provider: str) -> ProviderHealthSnapshot:
        with self._lock:
            rec = self._get_record(provider)
            now = datetime.now(UTC)
            self._maybe_exit_cooldown(rec, now)
            rec.success_count += 1
            rec.consecutive_failures = 0
            rec.consecutive_429s = 0
            if rec.state in (ProviderState.DEGRADED, ProviderState.UNHEALTHY):
                rec.state = ProviderState.HEALTHY
            return self._to_snapshot(provider, rec)

    def record_failure(
        self, provider: str, *, is_rate_limit: bool = False
    ) -> ProviderHealthSnapshot:
        with self._lock:
            rec = self._get_record(provider)
            now = datetime.now(UTC)
            self._maybe_exit_cooldown(rec, now)
            rec.failure_count += 1
            rec.consecutive_failures += 1
            rec.last_failure_at = now
            if is_rate_limit:
                rec.rate_limit_count += 1
                rec.consecutive_429s += 1
                if rec.consecutive_429s >= self.degraded_429_threshold:
                    rec.state = ProviderState.DEGRADED
            else:
                rec.consecutive_429s = 0

            if rec.consecutive_failures >= self.unhealthy_failure_threshold:
                rec.state = ProviderState.UNHEALTHY
                rec.state = ProviderState.COOLDOWN
                rec.cooldown_until = now + timedelta(seconds=self.cooldown_s)

            return self._to_snapshot(provider, rec)

    def all_snapshots(self) -> dict[str, ProviderHealthSnapshot]:
        with self._lock:
            now = datetime.now(UTC)
            out: dict[str, ProviderHealthSnapshot] = {}
            for provider, rec in self._records.items():
                self._maybe_exit_cooldown(rec, now)
                out[provider] = self._to_snapshot(provider, rec)
            return out


class RedisHealthStore(HealthStore):
    """Stub for future Redis-backed health store."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise NotImplementedError(
            "RedisHealthStore is not implemented; use InMemoryHealthStore"
        )

    def get(self, provider: str) -> ProviderHealthSnapshot:
        raise NotImplementedError

    def record_success(self, provider: str) -> ProviderHealthSnapshot:
        raise NotImplementedError

    def record_failure(
        self, provider: str, *, is_rate_limit: bool = False
    ) -> ProviderHealthSnapshot:
        raise NotImplementedError

    def all_snapshots(self) -> dict[str, ProviderHealthSnapshot]:
        raise NotImplementedError


class ProviderHealthManager:
    def __init__(self, store: HealthStore) -> None:
        self._store = store

    def allow(self, provider: str) -> bool:
        snap = self._store.get(provider)
        if snap.state == ProviderState.COOLDOWN:
            return False
        return True

    def record_success(self, provider: str) -> ProviderHealthSnapshot:
        return self._store.record_success(provider)

    def record_failure(
        self, provider: str, *, is_rate_limit: bool = False
    ) -> ProviderHealthSnapshot:
        return self._store.record_failure(provider, is_rate_limit=is_rate_limit)

    def snapshot(self, provider: str) -> ProviderHealthSnapshot:
        return self._store.get(provider)

    def all_snapshots(self) -> dict[str, ProviderHealthSnapshot]:
        return self._store.all_snapshots()

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
