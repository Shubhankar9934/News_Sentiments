"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.routes import (
    admin,
    analogs,
    dashboard,
    deliberation,
    dil,
    health,
    history,
    market_data,
    market_data_ws,
    research,
    summaries,
    websocket,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(dil.router, tags=["dil"])
api_router.include_router(research.router, tags=["research"])
api_router.include_router(deliberation.router, tags=["deliberation"])
api_router.include_router(history.router, tags=["history"])
api_router.include_router(analogs.router, tags=["analogs"])
api_router.include_router(summaries.router, tags=["summaries"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(market_data.ticker_router, tags=["market-data"])
api_router.include_router(market_data.dashboard_live_router, tags=["market-data"])
api_router.include_router(market_data.md_health_router, tags=["market-data"])
api_router.include_router(market_data_ws.router, tags=["market-data"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(websocket.router, tags=["websocket"])
