"""DIL operational health and resilience metrics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.deliberation.desk_config import ALL_DESK_KEYS, get_active_desks
from app.services.deliberation.llm_clients.registry import get_client_map
from app.services.dil_resilience.registry import get_resilience_gateway

router = APIRouter(prefix="/dil", tags=["dil"])


@router.get("/health")
async def dil_health() -> dict[str, Any]:
    """Expose provider health, circuit breakers, concurrency, and run metrics."""
    settings = get_settings()
    gateway = get_resilience_gateway(settings)
    snapshot = gateway.health_snapshot()

    client_map = get_client_map(settings)
    active_desks = get_active_desks(settings)

    snapshot["configured_providers"] = list(client_map.keys())
    snapshot["routing"]["desks_configured"] = len(active_desks)
    snapshot["routing"]["total_desk_keys"] = len(ALL_DESK_KEYS)
    snapshot["quorum_thresholds"] = {
        "desk_min_models": settings.dil_min_models,
        "assessment_min_members": settings.effective_assessment_min_members,
        "council_min_members": settings.effective_council_min_members,
    }

    return snapshot
