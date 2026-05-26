"""In-memory DIL metrics for observability."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * pct)
    idx = min(idx, len(sorted_vals) - 1)
    return round(sorted_vals[idx], 2)


@dataclass
class ProviderMetrics:
    requests: int = 0
    successes: int = 0
    failures: int = 0
    retries: int = 0
    failovers: int = 0
    rate_limit_count: int = 0
    cooldown_skips: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        total = self.requests or 1
        return {
            "requests": self.requests,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": round(self.successes / total, 4),
            "retries": self.retries,
            "failovers": self.failovers,
            "429_count": self.rate_limit_count,
            "cooldown_skips": self.cooldown_skips,
            "latency_p50_ms": _percentile(self.latencies_ms, 0.5),
            "latency_p95_ms": _percentile(self.latencies_ms, 0.95),
        }


@dataclass
class LastRunMetrics:
    assessment_degraded: bool = False
    council_degraded: bool = False
    assessment_valid: int = 0
    council_valid: int = 0
    desk_success: int = 0
    desk_failed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_degraded": self.assessment_degraded,
            "council_degraded": self.council_degraded,
            "assessment_valid": self.assessment_valid,
            "council_valid": self.council_valid,
            "desk_success": self.desk_success,
            "desk_failed": self.desk_failed,
        }


class DilMetricsCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._providers: dict[str, ProviderMetrics] = {}
        self._desks: dict[str, dict[str, int | float]] = {}
        self._assessment: dict[str, int] = {
            "valid_members": 0,
            "degraded_runs": 0,
            "quorum_failures": 0,
        }
        self._council: dict[str, int] = {
            "valid_voters": 0,
            "degraded_runs": 0,
            "quorum_failures": 0,
        }
        self._last_run = LastRunMetrics()
        self._routing_custom_chains = 0

    def _provider(self, name: str) -> ProviderMetrics:
        if name not in self._providers:
            self._providers[name] = ProviderMetrics()
        return self._providers[name]

    def record_request(
        self,
        provider: str,
        *,
        success: bool,
        latency_ms: float,
        is_rate_limit: bool = False,
        retried: bool = False,
    ) -> None:
        with self._lock:
            m = self._provider(provider)
            m.requests += 1
            if success:
                m.successes += 1
            else:
                m.failures += 1
            if is_rate_limit:
                m.rate_limit_count += 1
            if retried:
                m.retries += 1
            m.latencies_ms.append(latency_ms)
            if len(m.latencies_ms) > 500:
                m.latencies_ms = m.latencies_ms[-500:]

    def record_failover(self, provider: str) -> None:
        with self._lock:
            self._provider(provider).failovers += 1

    def record_retry(self, provider: str) -> None:
        with self._lock:
            self._provider(provider).retries += 1

    def record_cooldown_skip(self, provider: str) -> None:
        with self._lock:
            self._provider(provider).cooldown_skips += 1

    def record_desk(
        self,
        desk_key: str,
        *,
        success: bool,
        failover_count: int = 0,
        latency_ms: float = 0.0,
    ) -> None:
        with self._lock:
            if desk_key not in self._desks:
                self._desks[desk_key] = {
                    "success": 0,
                    "failed": 0,
                    "failover_count": 0,
                    "latency_ms_total": 0.0,
                    "runs": 0,
                }
            d = self._desks[desk_key]
            d["runs"] = int(d["runs"]) + 1
            if success:
                d["success"] = int(d["success"]) + 1
            else:
                d["failed"] = int(d["failed"]) + 1
            d["failover_count"] = int(d["failover_count"]) + failover_count
            d["latency_ms_total"] = float(d["latency_ms_total"]) + latency_ms

    def record_assessment_quorum(
        self,
        *,
        valid: int,
        degraded: bool,
        quorum_met: bool,
    ) -> None:
        with self._lock:
            self._assessment["valid_members"] = valid
            if degraded:
                self._assessment["degraded_runs"] = (
                    int(self._assessment["degraded_runs"]) + 1
                )
            if not quorum_met:
                self._assessment["quorum_failures"] = (
                    int(self._assessment["quorum_failures"]) + 1
                )
            self._last_run.assessment_valid = valid
            self._last_run.assessment_degraded = degraded

    def record_council_quorum(
        self,
        *,
        valid: int,
        degraded: bool,
        quorum_met: bool,
    ) -> None:
        with self._lock:
            self._council["valid_voters"] = valid
            if degraded:
                self._council["degraded_runs"] = int(self._council["degraded_runs"]) + 1
            if not quorum_met:
                self._council["quorum_failures"] = (
                    int(self._council["quorum_failures"]) + 1
                )
            self._last_run.council_valid = valid
            self._last_run.council_degraded = degraded

    def record_desk_batch(self, *, success: int, failed: int) -> None:
        with self._lock:
            self._last_run.desk_success = success
            self._last_run.desk_failed = failed

    def set_routing_custom_chains(self, count: int) -> None:
        with self._lock:
            self._routing_custom_chains = count

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "providers": {k: v.to_dict() for k, v in self._providers.items()},
                "desks": dict(self._desks),
                "assessments": dict(self._assessment),
                "councils": dict(self._council),
                "last_run": self._last_run.to_dict(),
                "routing": {"custom_chains": self._routing_custom_chains},
            }
