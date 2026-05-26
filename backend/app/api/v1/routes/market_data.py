"""Live IBKR market-data endpoints.

Powers the live half of the Reverse BWB Trading Workstation. Five routes:

    GET  /api/v1/tickers/{ticker}/market-data
    GET  /api/v1/tickers/{ticker}/options-opportunities
    GET  /api/v1/tickers/{ticker}/opportunity-explorer
    GET  /api/v1/tickers/{ticker}/opportunity-history
    GET  /api/v1/dashboard/live

All routes are pure DB reads — the IBKR worker is the only writer. They
serve sorted/filtered Reverse BWB opportunities without any artificial
top-N cap; the explorer endpoint adds pagination so even thousand-row
chains stay fast.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import get_settings
from app.core.dependencies import SessionDep
from app.core.rate_limit import limiter
from app.services.dashboard.watchlist import (
    ALL_WATCHLIST_TICKERS,
    is_watchlist_ticker,
)
from app.services.market_data.repository import MarketDataRepository
from app.services.market_data.schemas import (
    CandleListResponse,
    Candle1mResponse,
    DashboardLiveBundle,
    FeedStatus,
    MarketDataResponse,
    OpportunityExplorerResponse,
    OpportunityHistoryResponse,
    OptionsOpportunitiesResponse,
)


def _connection_status(request: Request) -> FeedStatus:
    """Map ``IbkrConnection.state`` onto the public ``feed_status`` vocab."""
    settings = get_settings()
    if not settings.ibkr_enabled:
        return "disconnected"
    ibkr = getattr(request.app.state, "ibkr", None)
    if ibkr is None:
        return "disconnected"
    state = getattr(ibkr, "state", "disconnected")
    if state == "connected":
        return "live"
    return "disconnected"


# --------------------------------------------------------------------------
# Per-ticker routes (mounted at /tickers/{ticker})
# --------------------------------------------------------------------------
ticker_router = APIRouter(prefix="/tickers")


@ticker_router.get(
    "/{ticker}/market-data",
    response_model=MarketDataResponse,
)
@limiter.limit(get_settings().rate_limit_summaries)
async def get_ticker_market_data(
    request: Request,
    ticker: str,
    session: SessionDep,
) -> MarketDataResponse:
    """Return the latest live quote for one watchlist ticker."""
    upper = ticker.upper()
    if not is_watchlist_ticker(upper):
        raise HTTPException(status_code=404, detail=f"{upper!r} is not on the watchlist")

    settings = get_settings()
    conn_status = _connection_status(request)

    # Try QuoteCache first (in-process dict → Redis); fall back to DB.
    quote_cache = getattr(request.app.state, "quote_cache", None)
    quote = None
    if quote_cache is not None:
        quote = await quote_cache.get(upper)
    if quote is None:
        repo = MarketDataRepository(session)
        quote = await repo.get_quote(
            upper,
            stale_threshold_s=settings.market_data_stale_threshold_s,
        )

    if quote is None:
        return MarketDataResponse(
            ticker=upper,
            feed_status=(
                "disconnected" if conn_status == "disconnected" else "unavailable"
            ),
        )

    final_status: FeedStatus = (
        "disconnected" if conn_status == "disconnected" else quote.feed_status
    )

    return MarketDataResponse(
        ticker=upper,
        price=quote.last_price,
        bid=quote.bid,
        ask=quote.ask,
        change_abs=quote.change_abs,
        change_pct=quote.change_pct,
        volume=quote.volume,
        prev_close=quote.prev_close,
        feed_status=final_status,
        updated_at=quote.updated_at,
    )


@ticker_router.get(
    "/{ticker}/options-opportunities",
    response_model=OptionsOpportunitiesResponse,
)
@limiter.limit(get_settings().rate_limit_summaries)
async def get_ticker_options_opportunities(
    request: Request,
    ticker: str,
    session: SessionDep,
    side: Literal["call", "put"] | None = Query(default=None),
    sort: str = Query(default="ranking_score"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> OptionsOpportunitiesResponse:
    """Return ALL live Reverse-BWB opportunities for one ticker.

    No artificial top-N cap — the Workstation generator stores every
    valid candidate. The default 500-row page is enough for the most
    liquid SPY chain; the explorer endpoint adds per-field filters.
    """
    upper = ticker.upper()
    if not is_watchlist_ticker(upper):
        raise HTTPException(status_code=404, detail=f"{upper!r} is not on the watchlist")

    settings = get_settings()
    repo = MarketDataRepository(session)
    bundle = await repo.get_opportunities(
        upper,
        stale_threshold_s=settings.market_data_stale_threshold_s,
        limit=limit,
        offset=offset,
        side=side,
        sort=sort,
        order=order,
    )

    conn_status = _connection_status(request)
    if bundle is None:
        return OptionsOpportunitiesResponse(
            ticker=upper,
            calls=[],
            puts=[],
            feed_status=(
                "disconnected" if conn_status == "disconnected" else "unavailable"
            ),
        )

    final_status: FeedStatus = (
        "disconnected" if conn_status == "disconnected" else bundle.feed_status
    )

    return OptionsOpportunitiesResponse(
        ticker=upper,
        calls=list(bundle.calls),
        puts=list(bundle.puts),
        call_version=bundle.call_version,
        put_version=bundle.put_version,
        updated_at=bundle.updated_at,
        feed_status=final_status,
    )


@ticker_router.get(
    "/{ticker}/opportunity-explorer",
    response_model=OpportunityExplorerResponse,
)
@limiter.limit(get_settings().rate_limit_summaries)
async def get_opportunity_explorer(
    request: Request,
    ticker: str,
    session: SessionDep,
    side: Literal["call", "put"] | None = Query(default=None),
    dte_min: int | None = Query(default=None, ge=0),
    dte_max: int | None = Query(default=None, ge=0),
    delta_min: float | None = Query(default=None),
    delta_max: float | None = Query(default=None),
    premium_min: float | None = Query(default=None),
    premium_max: float | None = Query(default=None),
    margin_min: float | None = Query(default=None),
    margin_max: float | None = Query(default=None),
    liquidity_min: int | None = Query(default=None, ge=0),
    credit_efficiency_min: float | None = Query(default=None),
    sort: str = Query(default="ranking_score"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
) -> OpportunityExplorerResponse:
    """Filterable, sortable opportunity grid for the Full Report.

    All filters are inclusive ranges; any unset filter is omitted from
    the WHERE clause. ``sort`` accepts: ``ranking_score``,
    ``credit_efficiency``, ``premium``, ``margin``, ``liquidity``,
    ``delta`` (alias for ``delta_pct``), ``expiry_days``. Pagination is
    keyed by ``limit`` + ``offset``.
    """
    upper = ticker.upper()
    if not is_watchlist_ticker(upper):
        raise HTTPException(status_code=404, detail=f"{upper!r} is not on the watchlist")

    settings = get_settings()
    repo = MarketDataRepository(session)
    conn_status = _connection_status(request)

    # The repository's get_opportunities applies sort + pagination directly;
    # filter predicates are layered on here via a fresh query to keep
    # the repository surface narrow.
    from sqlalchemy import desc, select

    from app.db.models.tables import TickerLiveOptionOpportunityModel

    stmt = select(TickerLiveOptionOpportunityModel).where(
        TickerLiveOptionOpportunityModel.ticker == upper
    )
    if side is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.side == side)
    if dte_min is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.expiry_days >= dte_min)
    if dte_max is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.expiry_days <= dte_max)
    if delta_min is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.delta_pct >= delta_min)
    if delta_max is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.delta_pct <= delta_max)
    if premium_min is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.premium >= premium_min)
    if premium_max is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.premium <= premium_max)
    if margin_min is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.init_margin >= margin_min)
    if margin_max is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.init_margin <= margin_max)
    if liquidity_min is not None:
        stmt = stmt.where(TickerLiveOptionOpportunityModel.liquidity >= liquidity_min)
    if credit_efficiency_min is not None:
        stmt = stmt.where(
            TickerLiveOptionOpportunityModel.credit_efficiency >= credit_efficiency_min
        )

    # Count total before applying limit/offset for pagination metadata.
    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = int((await session.execute(count_stmt)).scalar() or 0)

    # Sort + paginate.
    from app.services.market_data.repository import _resolve_sort_column

    sort_col = _resolve_sort_column(sort)
    if order == "asc":
        stmt = stmt.order_by(sort_col.asc().nullslast())
    else:
        stmt = stmt.order_by(sort_col.desc().nullslast())
    stmt = stmt.offset(int(offset)).limit(int(limit))

    rows = (await session.execute(stmt)).scalars().all()
    from app.services.market_data.repository import _row_to_live_opp

    final_status: FeedStatus = (
        "disconnected"
        if conn_status == "disconnected"
        else ("unavailable" if not rows else "live")
    )
    _ = settings  # retained for parity / future stale-threshold use

    return OpportunityExplorerResponse(
        ticker=upper,
        total=total,
        limit=int(limit),
        offset=int(offset),
        rows=[_row_to_live_opp(r) for r in rows],
        feed_status=final_status,
    )


@ticker_router.get(
    "/{ticker}/opportunity-history",
    response_model=OpportunityHistoryResponse,
)
@limiter.limit(get_settings().rate_limit_summaries)
async def get_opportunity_history(
    request: Request,
    ticker: str,
    session: SessionDep,
    snapshot_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    since: datetime | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
) -> OpportunityHistoryResponse:
    """Read rows from the append-only ``ticker_option_opportunity_history`` table.

    Either filter by ``snapshot_date`` (one trading day) or by ``since``
    (cumulative since timestamp). Defaults to most recent rows first.
    """
    upper = ticker.upper()
    if not is_watchlist_ticker(upper):
        raise HTTPException(status_code=404, detail=f"{upper!r} is not on the watchlist")

    repo = MarketDataRepository(session)
    rows, total = await repo.get_opportunity_history(
        upper,
        snapshot_date=snapshot_date,
        since=since,
        limit=limit,
        offset=offset,
    )
    _ = request  # rate limit dependency uses Request
    return OpportunityHistoryResponse(
        ticker=upper,
        total=total,
        limit=int(limit),
        offset=int(offset),
        rows=rows,
    )


@ticker_router.get(
    "/{ticker}/candles/1m",
    response_model=CandleListResponse,
)
@limiter.limit(get_settings().rate_limit_summaries)
async def get_candles_1m(
    request: Request,
    ticker: str,
    session: SessionDep,
    since: datetime | None = Query(
        default=None,
        description="Start of range (UTC). Defaults to 2 hours ago.",
    ),
    limit: int = Query(default=120, ge=1, le=1440),
) -> CandleListResponse:
    """Return 1-minute OHLCV candles for one watchlist ticker.

    Candles are generated by the live IBKR tick stream and flushed to
    ``market_candles_1m`` every ~60 s.  Results are in ascending ts order.
    At most 1440 candles (24 h) per request.
    """
    upper = ticker.upper()
    if not is_watchlist_ticker(upper):
        raise HTTPException(status_code=404, detail=f"{upper!r} is not on the watchlist")

    from datetime import timedelta, timezone

    if since is None:
        since = datetime.now(timezone.utc) - timedelta(hours=2)

    repo = MarketDataRepository(session)
    candles = await repo.get_candles_1m(upper, since=since, limit=limit)

    return CandleListResponse(
        ticker=upper,
        interval="1m",
        count=len(candles),
        candles=[
            Candle1mResponse(
                ticker=c.ticker,
                ts=c.ts,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for c in candles
        ],
    )


# --------------------------------------------------------------------------
# Health route (mounted at /market-data)
# --------------------------------------------------------------------------
md_health_router = APIRouter(prefix="/market-data")


@md_health_router.get(
    "/health",
    include_in_schema=True,
)
async def market_data_health(request: Request, session: SessionDep) -> dict:
    """Operational snapshot for the live market-data layer.

    Powers the trader-facing connection banner and ops dashboards. Cheap —
    one query per known table plus an in-memory poll of the worker.
    """
    settings = get_settings()
    repo = MarketDataRepository(session)
    versions = await repo.get_opportunity_versions(ALL_WATCHLIST_TICKERS)

    worker = getattr(request.app.state, "market_data_worker", None)
    opp_worker = getattr(request.app.state, "opportunity_worker", None)
    pubsub = getattr(request.app.state, "market_data_pubsub", None) or (
        worker.pubsub if worker is not None else None
    )

    whatif_budget_remaining: int | None = None
    if opp_worker is not None:
        try:
            whatif_budget_remaining = (
                await opp_worker.opp_service.margin_engine.budget.remaining()
            )
        except Exception:  # pragma: no cover - defensive
            whatif_budget_remaining = None

    return {
        "ibkr_enabled": settings.ibkr_enabled,
        "ibkr_state": getattr(getattr(request.app.state, "ibkr", None), "state", "disconnected"),
        "active_ws_clients": (pubsub.active_subscribers if pubsub else 0),
        "published_ticks": getattr(pubsub, "published_ticks", 0) if pubsub else 0,
        "published_versions": getattr(pubsub, "published_versions", 0) if pubsub else 0,
        "dropped_overflow": getattr(pubsub, "dropped_overflow", 0) if pubsub else 0,
        "whatif_budget_remaining": whatif_budget_remaining,
        "opportunity_versions": {
            ticker: {side: str(v) if v else None for side, v in by_side.items()}
            for ticker, by_side in versions.items()
        },
        "settings": {
            "dte": [settings.opp_dte_min, settings.opp_dte_max],
            "wing_strikes": [
                settings.opp_wing_min_strikes,
                settings.opp_wing_max_strikes,
            ],
            "min_leg_oi": settings.opp_min_leg_oi,
            "whatif_top_n": settings.opp_whatif_top_n,
            "whatif_max_per_min": settings.opp_whatif_max_per_min,
            "recalc_price_pct": settings.opp_recalc_price_pct,
            "recalc_iv_pct": settings.opp_recalc_iv_pct,
            "recalc_max_age_s": settings.opp_recalc_max_age_s,
        },
    }


# --------------------------------------------------------------------------
# Bulk route (mounted at /dashboard/live)
# --------------------------------------------------------------------------
dashboard_live_router = APIRouter(prefix="/dashboard")


@dashboard_live_router.get(
    "/live",
    response_model=DashboardLiveBundle,
)
@limiter.limit(get_settings().rate_limit_summaries)
async def get_dashboard_live(
    request: Request,
    session: SessionDep,
) -> DashboardLiveBundle:
    """Return live quote + options-opportunities for every watchlist ticker.

    Frontend polls this every ~4s (or skips polling when the WebSocket
    is connected). The bundle includes ``opportunity_version`` UUIDs so
    clients can detect drift between socket reconnects.
    """
    settings = get_settings()
    repo = MarketDataRepository(session)
    conn_status = _connection_status(request)
    bundle = await repo.get_dashboard_live_bundle(
        ALL_WATCHLIST_TICKERS,
        stale_threshold_s=settings.market_data_stale_threshold_s,
        connection_status=conn_status,
    )
    return bundle
