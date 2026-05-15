"""Health and readiness endpoints."""

from fastapi import APIRouter, Request

from app.core.constants import API_VERSION
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    pool_ok = getattr(request.app.state, "db_ok", False)
    redis_ok = getattr(request.app.state, "redis_ok", False)
    qd = getattr(request.app.state, "qdrant", None)
    return HealthResponse(
        status="ok",
        version=API_VERSION,
        db=pool_ok,
        redis=redis_ok,
        qdrant=qd is not None,
    )


@router.get("/ready")
async def ready(request: Request) -> dict:
    db_ok = getattr(request.app.state, "db_ok", False)
    if not db_ok:
        return {"ready": False, "reason": "database_unavailable"}
    return {"ready": True}
