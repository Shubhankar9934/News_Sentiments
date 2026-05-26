"""Pydantic schemas for the live IBKR market-data layer.

These schemas are completely separate from
``app.services.dashboard.schemas`` so a price tick can never accidentally
flow into the frozen analysis snapshot. The ``ReverseBwbSummary``,
``DashboardTickerCard`` and friends remain the canonical analysis-snapshot
contract; the schemas defined here are the canonical live-feed contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------
# Vocabularies
# --------------------------------------------------------------------------
SideLiteral = Literal["call", "put"]

# Init-margin source — explicit so the UI can show an "estimated" badge for
# rows where we couldn't burn a WhatIf round-trip.
MarginSourceLiteral = Literal["deterministic", "whatif"]

# Liquidity is a pure integer (min(OI per leg)) in the Workstation schema.
# The legacy categorical label is kept ONLY for the placeholder snapshot
# table and its API; the live table never uses it.
LegacyLiquidityGrade = Literal["Excellent", "Good", "Average", "Poor"]
# Back-compat alias — old code (and the frontend) imported this name.
LiquidityGrade = LegacyLiquidityGrade

# ``feed_status`` reflects the live worker's view per ticker:
#   - live          : last tick within MARKET_DATA_STALE_THRESHOLD_S
#   - stale         : worker is connected but has not received a tick
#                     for that ticker recently (e.g. halted symbol)
#   - disconnected  : IBKR connection is down or IBKR_ENABLED=false
#   - unavailable   : never had data (worker hasn't run yet for this row)
FeedStatus = Literal["live", "stale", "disconnected", "unavailable"]


# --------------------------------------------------------------------------
# Live quote
# --------------------------------------------------------------------------
class LiveQuote(BaseModel):
    """One row of ``ticker_market_data``.

    All numerics are nullable because IBKR can return partial ticks
    (e.g. last price only on illiquid names, or bid/ask only outside
    market hours).
    """

    ticker: str
    last_price: float | None = None
    bid: float | None = None
    ask: float | None = None
    change_abs: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    prev_close: float | None = None
    feed_status: FeedStatus = "unavailable"
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Live opportunity (Reverse BWB Workstation schema)
# --------------------------------------------------------------------------
class LiveOpportunity(BaseModel):
    """One row of ``ticker_live_option_opportunities``.

    The schema is intentionally rich — the dashboard card shows the
    summary columns (combo / exp / delta / premium / margin / liquidity /
    credit_efficiency / score) while the Full Report opportunity explorer
    consumes per-leg OI/volume/IV and the strike triplet.

    Sign convention for ``premium``:
        * Negative = credit received (the BWB's typical net-credit case).
        * Positive = debit paid.
    """

    ticker: str
    side: SideLiteral
    rank: int = Field(ge=0)
    combo: str
    strike_long_wing_a: float | None = None
    strike_short_body: float | None = None
    strike_long_wing_b: float | None = None
    expiration: str
    expiry_days: int | None = None
    delta_pct: float | None = None
    premium: float
    init_margin: float | None = None
    maint_margin: float | None = None
    init_margin_source: MarginSourceLiteral = "deterministic"
    liquidity: int = Field(ge=0, default=0)
    minimum_open_interest: int | None = None
    minimum_volume: int | None = None
    oi_leg1: int | None = None
    oi_leg2: int | None = None
    oi_leg3: int | None = None
    vol_leg1: int | None = None
    vol_leg2: int | None = None
    vol_leg3: int | None = None
    iv_leg1: float | None = None
    iv_leg2: float | None = None
    iv_leg3: float | None = None
    mid_leg1: float | None = None
    mid_leg2: float | None = None
    mid_leg3: float | None = None
    credit_efficiency: float | None = None
    ranking_score: float | None = None
    underlying_price: float | None = None
    iv: float | None = None
    opportunity_version: UUID | None = None
    generated_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class LiveOpportunityBundle(BaseModel):
    """``calls`` + ``puts`` per ticker — directly maps to the UI tables.

    The bundle also carries the per-side ``opportunity_version`` UUID so
    clients receiving a ``opportunity_version`` WebSocket event can detect
    whether their cached rows are already up-to-date.
    """

    calls: list[LiveOpportunity] = Field(default_factory=list)
    puts: list[LiveOpportunity] = Field(default_factory=list)
    call_version: UUID | None = None
    put_version: UUID | None = None
    updated_at: datetime | None = None
    feed_status: FeedStatus = "unavailable"

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Bulk dashboard live response (used by ``GET /api/v1/dashboard/live``)
# --------------------------------------------------------------------------
class DashboardLiveTickerEntry(BaseModel):
    """One ticker's live slice within the bulk dashboard response."""

    ticker: str
    quote: LiveQuote | None = None
    opportunities: LiveOpportunityBundle | None = None

    model_config = ConfigDict(extra="forbid")


class DashboardLiveBundle(BaseModel):
    """Full bulk live response for the 12-ticker grid.

    The frontend polls this every ~4s. The ``feed_status`` field at the top
    level reflects the IBKR connection state itself; per-ticker
    ``quote.feed_status`` may further narrow that to ``stale`` for a
    halted/illiquid name. Updated-at fields let the UI show "as of HH:MM:SS"
    if needed.
    """

    feed_status: FeedStatus
    prices_updated_at: datetime | None = None
    opportunities_updated_at: datetime | None = None
    tickers: dict[str, DashboardLiveTickerEntry] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# Single-ticker response shapes (used by per-ticker endpoints)
# --------------------------------------------------------------------------
class MarketDataResponse(BaseModel):
    """Response for ``GET /api/v1/tickers/{ticker}/market-data``."""

    ticker: str
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    change_abs: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    prev_close: float | None = None
    feed_status: FeedStatus
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class OptionsOpportunitiesResponse(BaseModel):
    """Response for ``GET /api/v1/tickers/{ticker}/options-opportunities``.

    Returns ALL currently active rows for the ticker (no top-N cap). The
    explorer endpoint adds filter/sort/pagination on top of the same row
    schema.
    """

    ticker: str
    calls: list[LiveOpportunity] = Field(default_factory=list)
    puts: list[LiveOpportunity] = Field(default_factory=list)
    call_version: UUID | None = None
    put_version: UUID | None = None
    updated_at: datetime | None = None
    feed_status: FeedStatus

    model_config = ConfigDict(extra="forbid")


class OpportunityExplorerResponse(BaseModel):
    """Response for ``GET /api/v1/tickers/{ticker}/opportunity-explorer``.

    Adds pagination metadata for the Full Report's filter/sort grid.
    """

    ticker: str
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    rows: list[LiveOpportunity] = Field(default_factory=list)
    feed_status: FeedStatus

    model_config = ConfigDict(extra="forbid")


class OpportunityHistoryEntry(BaseModel):
    """One row of ``ticker_option_opportunity_history``.

    Identical column set to ``LiveOpportunity`` plus a ``snapshot_date``
    so the explorer can pivot by trading day.
    """

    id: UUID
    ticker: str
    side: SideLiteral
    combo: str
    strike_long_wing_a: float
    strike_short_body: float
    strike_long_wing_b: float
    expiration: str
    expiry_days: int
    delta_pct: float | None = None
    premium: float
    init_margin: float | None = None
    maint_margin: float | None = None
    init_margin_source: MarginSourceLiteral = "deterministic"
    liquidity: int = Field(ge=0, default=0)
    minimum_open_interest: int | None = None
    minimum_volume: int | None = None
    oi_leg1: int | None = None
    oi_leg2: int | None = None
    oi_leg3: int | None = None
    vol_leg1: int | None = None
    vol_leg2: int | None = None
    vol_leg3: int | None = None
    iv_leg1: float | None = None
    iv_leg2: float | None = None
    iv_leg3: float | None = None
    mid_leg1: float | None = None
    mid_leg2: float | None = None
    mid_leg3: float | None = None
    credit_efficiency: float | None = None
    ranking_score: float | None = None
    underlying_price: float | None = None
    iv: float | None = None
    opportunity_version: UUID
    generated_at: datetime
    snapshot_date: str

    model_config = ConfigDict(extra="forbid")


class OpportunityHistoryResponse(BaseModel):
    """Response for ``GET /api/v1/tickers/{ticker}/opportunity-history``."""

    ticker: str
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    rows: list[OpportunityHistoryEntry] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------
# 1-minute candle schemas (used by ``GET /api/v1/tickers/{ticker}/candles/1m``)
# --------------------------------------------------------------------------
class Candle1mResponse(BaseModel):
    """One 1-minute OHLCV candle."""

    ticker: str
    ts: datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None

    model_config = ConfigDict(extra="forbid")


class CandleListResponse(BaseModel):
    """Response for ``GET /api/v1/tickers/{ticker}/candles/1m``."""

    ticker: str
    interval: str = "1m"
    count: int = Field(ge=0)
    candles: list[Candle1mResponse] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
