"""Process-local singleton wiring for DIL resilience components."""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.services.dil_resilience.circuit_breaker import CircuitBreakerRegistry
from app.services.dil_resilience.concurrency import LlmConcurrencyManager
from app.services.dil_resilience.gateway import ResilienceGateway
from app.services.dil_resilience.health import InMemoryHealthStore, ProviderHealthManager
from app.services.dil_resilience.metrics import DilMetricsCollector
from app.services.dil_resilience.retry import RetryAfterHandler
from app.services.dil_resilience.routing import RoutingConfig

_gateway: ResilienceGateway | None = None


def get_resilience_gateway(settings: Settings | None = None) -> ResilienceGateway:
    global _gateway
    if _gateway is None:
        _gateway = _build_gateway(settings or get_settings())
    return _gateway


def reset_resilience_registry(settings: Settings | None = None) -> ResilienceGateway:
    """Reset singleton (tests)."""
    global _gateway
    _gateway = _build_gateway(settings or get_settings())
    return _gateway


def _build_gateway(settings: Settings) -> ResilienceGateway:
    store = InMemoryHealthStore(
        degraded_429_threshold=settings.dil_health_degraded_429_threshold,
        unhealthy_failure_threshold=settings.dil_health_unhealthy_failure_threshold,
        cooldown_s=settings.dil_provider_cooldown_s,
    )
    health = ProviderHealthManager(store)
    breakers = CircuitBreakerRegistry(
        health,
        open_duration_s=settings.dil_cb_open_duration_s,
        probe_interval_s=settings.dil_cb_probe_interval_s,
        failure_threshold=settings.dil_health_unhealthy_failure_threshold,
    )
    concurrency = LlmConcurrencyManager(settings.dil_max_concurrent_llm_requests)
    retry = RetryAfterHandler(
        max_retries=settings.dil_429_max_retries,
        max_wait_s=float(settings.dil_429_max_wait_s),
    )
    metrics = DilMetricsCollector()
    routing = RoutingConfig(settings)
    metrics.set_routing_custom_chains(routing.custom_chain_count)
    return ResilienceGateway(
        enabled=settings.dil_resilience_enabled,
        concurrency=concurrency,
        retry=retry,
        health=health,
        breakers=breakers,
        metrics=metrics,
        routing=routing,
    )
