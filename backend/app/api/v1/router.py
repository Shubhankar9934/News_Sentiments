"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.routes import admin, analogs, deliberation, health, history, research, websocket

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(research.router, tags=["research"])
api_router.include_router(deliberation.router, tags=["deliberation"])
api_router.include_router(history.router, tags=["history"])
api_router.include_router(analogs.router, tags=["analogs"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(websocket.router, tags=["websocket"])
