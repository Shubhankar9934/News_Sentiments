"""Deliberation polling API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.core.dependencies import SessionDep
from app.core.rate_limit import limiter
from app.db.repositories.deliberation_repository import DeliberationRepository

router = APIRouter()


@router.get("/reports/{report_id}/deliberation")
@limiter.limit(get_settings().rate_limit_default)
async def get_deliberation(
    request: Request,
    report_id: str,
    session: SessionDep,
):
    try:
        rid = uuid.UUID(report_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid report_id") from e

    repo = DeliberationRepository(session)
    row = await repo.get_report_by_id(rid)
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    layer = (row.report_json or {}).get("deliberation_layer")
    if not layer:
        return {"status": "unavailable", "report_id": report_id}

    from app.services.deliberation.runner import schedule_deliberation_if_stale

    schedule_deliberation_if_stale(report_id, layer)

    return {"report_id": report_id, **layer}
