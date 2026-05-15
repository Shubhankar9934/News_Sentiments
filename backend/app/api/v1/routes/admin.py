"""Operational admin (non-destructive)."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import AdminInfo

router = APIRouter()


@router.get("/info", response_model=AdminInfo)
async def admin_info() -> AdminInfo:
    s = get_settings()
    return AdminInfo(environment=s.app_env, api_prefix=s.api_v1_prefix)
