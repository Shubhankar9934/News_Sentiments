"""Tests for provider health manager."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.dil_resilience.health import (
    InMemoryHealthStore,
    ProviderHealthManager,
    ProviderState,
)


def test_consecutive_429s_mark_degraded() -> None:
    store = InMemoryHealthStore(degraded_429_threshold=3)
    mgr = ProviderHealthManager(store)
    for _ in range(3):
        mgr.record_failure("groq", is_rate_limit=True)
    snap = mgr.snapshot("groq")
    assert snap.state == ProviderState.DEGRADED
    assert snap.consecutive_429s == 3


def test_consecutive_failures_enter_cooldown() -> None:
    store = InMemoryHealthStore(unhealthy_failure_threshold=5, cooldown_s=300)
    mgr = ProviderHealthManager(store)
    for _ in range(5):
        mgr.record_failure("gpt")
    snap = mgr.snapshot("gpt")
    assert snap.state == ProviderState.COOLDOWN
    assert not mgr.allow("gpt")


def test_success_resets_counters() -> None:
    store = InMemoryHealthStore(degraded_429_threshold=2)
    mgr = ProviderHealthManager(store)
    mgr.record_failure("claude", is_rate_limit=True)
    mgr.record_failure("claude", is_rate_limit=True)
    assert mgr.snapshot("claude").state == ProviderState.DEGRADED
    mgr.record_success("claude")
    assert mgr.snapshot("claude").state == ProviderState.HEALTHY
    assert mgr.snapshot("claude").consecutive_429s == 0


def test_cooldown_expires() -> None:
    store = InMemoryHealthStore(unhealthy_failure_threshold=1, cooldown_s=1)
    mgr = ProviderHealthManager(store)
    mgr.record_failure("deepseek")
    assert not mgr.allow("deepseek")
    rec = store._get_record("deepseek")  # noqa: SLF001
    rec.cooldown_until = datetime.now(UTC) - timedelta(seconds=1)
    assert mgr.allow("deepseek")


def test_filter_chain_last_resort() -> None:
    store = InMemoryHealthStore(unhealthy_failure_threshold=1, cooldown_s=300)
    mgr = ProviderHealthManager(store)
    mgr.record_failure("gpt")
    chain = ("gpt", "claude")
    filtered = mgr.filter_chain(chain)
    assert filtered == ["claude"]
    mgr.record_failure("claude")
    assert mgr.filter_chain(chain) == list(chain)
