"""Reverse BWB Intelligence Dashboard endpoints.

Four routes power the multi-ticker grid:

    GET  /api/v1/dashboard/tickers             — full snapshot for grid mount
    GET  /api/v1/dashboard/tickers/{ticker}    — single ticker card
    POST /api/v1/dashboard/refresh             — kick a sequential batch run
    POST /api/v1/dashboard/refresh/{ticker}    — kick a single-ticker refresh

The batch is owned by ``WatchlistBatchService`` (one instance per app
state). Refresh endpoints return 409 when a batch is already running so
the UI can render a "queued" state without polluting the in-process
state.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.core.dependencies import SessionDep
from app.core.rate_limit import limiter
from app.db.repositories.dashboard_repository import DashboardRepository
from app.services.dashboard.schemas import (
    DashboardTickerCard,
    DashboardTickerReportResponse,
    DashboardTickersResponse,
    WatchlistBatchStatus,
)
from app.services.dashboard.watchlist import is_watchlist_ticker
from app.services.dashboard.watchlist_batch import WatchlistBatchService

router = APIRouter(prefix="/dashboard")


def _get_batch_service(request: Request) -> WatchlistBatchService:
    """Resolve (and lazily create) the per-app batch service singleton."""

    batch = getattr(request.app.state, "watchlist_batch", None)
    if isinstance(batch, WatchlistBatchService):
        return batch
    settings = get_settings()
    return WatchlistBatchService.from_app_state(request.app, settings)


def _empty_status() -> WatchlistBatchStatus:
    from app.services.dashboard.watchlist import ALL_WATCHLIST_TICKERS

    return WatchlistBatchStatus(total=len(ALL_WATCHLIST_TICKERS))


@router.get("/tickers", response_model=DashboardTickersResponse)
@limiter.limit(get_settings().rate_limit_summaries)
async def get_dashboard_tickers(
    request: Request,
    session: SessionDep,
) -> DashboardTickersResponse:
    """Return the canonical 12-ticker grid snapshot plus batch status."""

    repo = DashboardRepository(session)
    cards = await repo.list_dashboard_cards()
    try:
        status = _get_batch_service(request).status
    except Exception:  # pragma: no cover - defensive
        status = _empty_status()
    return DashboardTickersResponse(status=status, cards=cards)


@router.get("/tickers/{ticker}", response_model=DashboardTickerCard)
@limiter.limit(get_settings().rate_limit_summaries)
async def get_dashboard_ticker(
    request: Request,
    ticker: str,
    session: SessionDep,
) -> DashboardTickerCard:
    upper = ticker.upper()
    if not is_watchlist_ticker(upper):
        raise HTTPException(status_code=404, detail=f"{upper!r} is not on the watchlist")
    card = await DashboardRepository(session).get_dashboard_card(upper)
    if card is None:
        raise HTTPException(status_code=404, detail=f"No dashboard data for {upper}")
    return card


@router.get("/tickers/{ticker}/report", response_model=DashboardTickerReportResponse)
@limiter.limit(get_settings().rate_limit_summaries)
async def get_dashboard_ticker_report(
    request: Request,
    ticker: str,
    session: SessionDep,
) -> DashboardTickerReportResponse:
    """Return the full persisted report snapshot for a watchlist ticker."""

    upper = ticker.upper()
    if not is_watchlist_ticker(upper):
        raise HTTPException(status_code=404, detail=f"{upper!r} is not on the watchlist")
    payload = await DashboardRepository(session).get_ticker_report(upper)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No persisted report for {upper}")
    return payload


@router.post("/refresh", response_model=WatchlistBatchStatus, status_code=202)
@limiter.limit(get_settings().rate_limit_default)
async def trigger_dashboard_refresh(request: Request) -> WatchlistBatchStatus:
    """Schedule a sequential refresh of every watchlist ticker.

    Returns 202 with the current status. If a batch is already running,
    responds 409 so the UI can show a queued indicator without competing
    with the in-flight job.
    """

    batch = _get_batch_service(request)
    asyncio.create_task(batch.run_once())
    return batch.status


@router.post(
    "/refresh/{ticker}",
    response_model=WatchlistBatchStatus,
    status_code=202,
)
@limiter.limit(get_settings().rate_limit_research)
async def trigger_dashboard_refresh_ticker(
    request: Request,
    ticker: str,
) -> WatchlistBatchStatus:
    upper = ticker.upper()
    if not is_watchlist_ticker(upper):
        raise HTTPException(status_code=404, detail=f"{upper!r} is not on the watchlist")
    batch = _get_batch_service(request)
    status = await batch.run_single(upper)
    return status
