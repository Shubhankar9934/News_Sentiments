"""Orchestrates pre/post LLM call resilience hooks."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from app.services.dil_resilience.context import dil_role_context
from app.services.dil_resilience.retry import RateLimitError

if TYPE_CHECKING:
    from app.services.dil_resilience.circuit_breaker import CircuitBreakerRegistry
    from app.services.dil_resilience.concurrency import LlmConcurrencyManager
    from app.services.dil_resilience.health import ProviderHealthManager
    from app.services.dil_resilience.metrics import DilMetricsCollector
    from app.services.dil_resilience.retry import RetryAfterHandler
    from app.services.dil_resilience.routing import RoutingConfig

log = structlog.get_logger(__name__)


class ResilienceGateway:
    def __init__(
        self,
        *,
        enabled: bool,
        concurrency: LlmConcurrencyManager,
        retry: RetryAfterHandler,
        health: ProviderHealthManager,
        breakers: CircuitBreakerRegistry,
        metrics: DilMetricsCollector,
        routing: RoutingConfig,
    ) -> None:
        self.enabled = enabled
        self.concurrency = concurrency
        self.retry = retry
        self.health = health
        self.breakers = breakers
        self.metrics = metrics
        self.routing = routing

    def filter_provider_chain(
        self,
        chain: tuple[str, ...] | list[str],
    ) -> list[str]:
        if not self.enabled:
            return list(chain)
        health_filtered = self.health.filter_chain(chain)
        breaker_filtered = self.breakers.filter_chain(health_filtered)
        skipped = set(chain) - set(breaker_filtered)
        for p in skipped:
            self.metrics.record_cooldown_skip(p)
        return breaker_filtered

    async def before_request(self, provider: str) -> None:
        if not self.enabled:
            return
        role = dil_role_context.get()
        await self.concurrency.acquire(provider, role)

    async def after_request(
        self,
        provider: str,
        *,
        success: bool,
        latency_ms: float,
        is_rate_limit: bool = False,
        retried: bool = False,
    ) -> None:
        if not self.enabled:
            return
        await self.concurrency.release()
        self.metrics.record_request(
            provider,
            success=success,
            latency_ms=latency_ms,
            is_rate_limit=is_rate_limit,
            retried=retried,
        )
        if success:
            self.health.record_success(provider)
            self.breakers.record_success(provider)
        else:
            self.health.record_failure(provider, is_rate_limit=is_rate_limit)
            self.breakers.record_failure(provider)

    async def handle_429(
        self,
        provider: str,
        status: int,
        headers: dict[str, str] | None,
        body: str,
        attempt: int,
    ) -> bool:
        """Return True if caller should retry same provider."""
        if not self.enabled:
            return False
        if attempt >= self.retry.max_retries:
            return False
        if self.retry.is_non_retryable_quota(body):
            log.info(
                "dil.resilience.retry.skip",
                provider=provider,
                reason="quota_exhausted",
            )
            return False
        delay = self.retry.parse_retry_after(provider, status, headers, body)
        self.metrics.record_retry(provider)
        self.health.record_failure(provider, is_rate_limit=True)
        await self.retry.sleep_before_retry(provider, attempt + 1, delay)
        return True

    def raise_rate_limit(self, provider: str, status: int, body: str) -> None:
        raise RateLimitError(provider, status, body[:500])

    def health_snapshot(self) -> dict[str, Any]:
        providers = {
            k: v.to_dict() for k, v in self.health.all_snapshots().items()
        }
        breakers = {
            k: v.to_dict() for k, v in self.breakers.all_snapshots().items()
        }
        metrics = self.metrics.snapshot()
        return {
            "resilience_enabled": self.enabled,
            "providers": providers,
            "circuit_breakers": breakers,
            "concurrency": {
                "max": self.concurrency.stats.max_concurrent,
                "active": self.concurrency.stats.active,
                "waiting": self.concurrency.stats.waiting,
            },
            "routing": metrics.get("routing", {}),
            "assessments": metrics.get("assessments", {}),
            "councils": metrics.get("councils", {}),
            "last_run": metrics.get("last_run", {}),
            "provider_metrics": metrics.get("providers", {}),
            "desks": metrics.get("desks", {}),
        }
