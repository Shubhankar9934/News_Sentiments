"""DIL production resilience — concurrency, retry, health, circuit breakers."""

from app.services.dil_resilience.context import dil_role_context, set_dil_role_context
from app.services.dil_resilience.executor import execute_with_failover
from app.services.dil_resilience.gateway import ResilienceGateway
from app.services.dil_resilience.quorum import QuorumEvaluator, QuorumResult
from app.services.dil_resilience.registry import get_resilience_gateway, reset_resilience_registry

__all__ = [
    "QuorumEvaluator",
    "QuorumResult",
    "ResilienceGateway",
    "execute_with_failover",
    "get_resilience_gateway",
    "dil_role_context",
    "reset_resilience_registry",
    "set_dil_role_context",
]
