"""WebSocket: streaming research progress (per-connection pipeline)."""

import json
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.orchestration.pipeline import ResearchPipelineService
from app.services.qdrant.store import QdrantStoreService

log = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/research-progress")
async def research_progress(ws: WebSocket) -> None:
    await ws.accept()
    settings = get_settings()
    try:
        while True:
            raw = await ws.receive_text()
            msg: dict[str, Any] = json.loads(raw)
            if msg.get("action") != "run":
                await ws.send_json({"type": "error", "detail": "unsupported_action"})
                continue
            ticker = str(msg.get("ticker", "")).strip().upper()
            days = int(msg.get("days", 7))
            if not ticker:
                await ws.send_json({"type": "error", "detail": "missing_ticker"})
                continue

            qdrant: QdrantStoreService | None = None
            try:
                qdrant = QdrantStoreService(settings)
            except Exception as e:
                log.warning("ws.qdrant_unavailable", error=str(e))

            async def on_progress(stage: str, message: str) -> None:
                await ws.send_json({"type": "progress", "stage": stage, "message": message})

            async with SessionLocal() as session:
                pipeline = ResearchPipelineService(
                    session=session,
                    settings=settings,
                    qdrant=qdrant,
                    cache=None,
                )
                try:
                    report = await pipeline.run(ticker, days, on_progress=on_progress)
                    await ws.send_json({"type": "result", "data": report})
                except Exception as e:
                    log.exception("ws.pipeline_failed")
                    await ws.send_json({"type": "error", "detail": str(e)})
    except WebSocketDisconnect:
        return
