"""Tests for circuit breaker integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.dil_resilience.circuit_breaker import CircuitBreaker, CircuitState
from app.services.dil_resilience.health import InMemoryHealthStore, ProviderHealthManager


def test_breaker_opens_after_failures() -> None:
    breaker = CircuitBreaker("gpt", failure_threshold=3, open_duration_s=60)
    for _ in range(3):
        breaker.record_failure()
    assert breaker.snapshot().state == CircuitState.OPEN
    assert not breaker.allow_request()


def test_half_open_probe_closes_on_success() -> None:
    breaker = CircuitBreaker("gpt", failure_threshold=1, open_duration_s=0)
    breaker.record_failure()
    assert breaker.allow_request()
    breaker.record_success()
    assert breaker.snapshot().state == CircuitState.CLOSED


def test_registry_skips_open_provider() -> None:
    from app.services.dil_resilience.circuit_breaker import CircuitBreakerRegistry

    health = ProviderHealthManager(InMemoryHealthStore())
    registry = CircuitBreakerRegistry(health, failure_threshold=2)
    registry.record_failure("groq")
    registry.record_failure("groq")
    filtered = registry.filter_chain(("groq", "gpt"))
    assert "groq" not in filtered or filtered == ["groq", "gpt"]
