"""Live IBKR market-data service stack.

This package is the live-data half of the dashboard's two-domain architecture:

    services/dashboard/    — frozen analysis snapshots (only refreshed on
                             user-triggered Re-Run Analysis)
    services/market_data/  — continuous live IBKR feed (this package)

A single IBKR Gateway connection owned by ``IbkrConnection`` feeds both the
quote stream (``MarketDataService.subscribe_quotes``) and the periodic
options-opportunity refresh (``OptionsOpportunityService.generate``). The
``MarketDataWorker`` runs both loops in the FastAPI process.

The repository writes only to ``ticker_market_data`` and
``ticker_live_option_opportunities``; it never touches the analysis
snapshot tables. This separation is enforced by static reference: there is
no import path from this package to ``app.services.dashboard.repository``
or vice versa.
"""

from app.services.market_data.ibkr_connection import IbkrConnection, IbkrConnectionState
from app.services.market_data.repository import MarketDataRepository
from app.services.market_data.schemas import (
    LiveOpportunity,
    LiveOpportunityBundle,
    LiveQuote,
    DashboardLiveBundle,
    DashboardLiveTickerEntry,
    FeedStatus,
    SideLiteral,
)

__all__ = [
    "IbkrConnection",
    "IbkrConnectionState",
    "MarketDataRepository",
    "LiveOpportunity",
    "LiveOpportunityBundle",
    "LiveQuote",
    "DashboardLiveBundle",
    "DashboardLiveTickerEntry",
    "FeedStatus",
    "SideLiteral",
]
