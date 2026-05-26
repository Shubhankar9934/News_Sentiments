"""ORM models aligned with legacy PostgreSQL schema."""

import uuid
from datetime import datetime
from typing import Any

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RawArticleModel(Base):
    __tablename__ = "raw_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    external_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class ProcessedArticleModel(Base):
    __tablename__ = "processed_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    raw_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_articles.id"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    sentiment_label: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str | None] = mapped_column(Text)
    reliability_score: Mapped[int | None] = mapped_column(Integer)
    impact_score: Mapped[float | None] = mapped_column(Float)
    abnormal_return: Mapped[float | None] = mapped_column(Float)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    cluster_id: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class OhlcvBarModel(Base):
    __tablename__ = "ohlcv_bars"
    __table_args__ = (
        UniqueConstraint("ticker", "timestamp", "timeframe", name="uq_ohlcv_ticker_ts_tf"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, default="1d")
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger)


class ResearchReportModel(Base):
    __tablename__ = "research_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    time_window: Mapped[str | None] = mapped_column(Text)
    report_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    data_mode: Mapped[str | None] = mapped_column(Text)
    articles_ct: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class DeliberationRunModel(Base):
    __tablename__ = "deliberation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_reports.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    run_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    models_used: Mapped[list[str] | None] = mapped_column(JSONB)
    layer_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # PR8 additive — calibration lineage columns. Populated from consensus
    # synthesis on completion; outcome columns stay NULL until a follow-up
    # job ingests realised returns.
    consensus_stance: Mapped[str | None] = mapped_column(Text)
    reconciled_label: Mapped[str | None] = mapped_column(Text)
    consensus_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    directional_conviction: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    consensus_strength: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    agreement_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    divergence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    contradiction_density: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    uncertainty: Mapped[str | None] = mapped_column(Text)
    primary_risks: Mapped[list[Any] | None] = mapped_column(JSONB)
    outcome_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    realized_return: Mapped[Decimal | None] = mapped_column(Numeric)
    outcome_label: Mapped[str | None] = mapped_column(Text)
    calibration_score: Mapped[Decimal | None] = mapped_column(Numeric)


class TickerReportModel(Base):
    """Latest-only research-report snapshot keyed by ticker.

    One row per watchlist ticker; refreshed via upsert by the
    ``WatchlistBatchService``. This is intentionally denormalized from
    ``research_reports`` so the dashboard can JOIN by ticker without a
    ``DISTINCT ON`` / correlated subquery. The full append-only history still
    lives in ``research_reports`` and is unchanged.
    """

    __tablename__ = "ticker_reports"
    __table_args__ = (
        UniqueConstraint("ticker", name="uq_ticker_reports_ticker"),
        Index("ix_ticker_reports_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    research_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_reports.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(Text)
    report_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class TickerReverseBwbSummaryModel(Base):
    """LLM-synthesised Reverse BWB summary, latest per ticker."""

    __tablename__ = "ticker_reverse_bwb_summary"
    __table_args__ = (
        UniqueConstraint("ticker", name="uq_ticker_reverse_bwb_summary_ticker"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    ticker_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ticker_reports.id"), nullable=True
    )

    decision: Mapped[str] = mapped_column(Text, nullable=False)
    credit_safety_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(Text, nullable=False)

    today_outlook: Mapped[str] = mapped_column(Text, nullable=False)
    next_3d_outlook: Mapped[str] = mapped_column(Text, nullable=False)

    chance_up_2_3_pct: Mapped[str] = mapped_column(Text, nullable=False)
    chance_down_2_3_pct: Mapped[str] = mapped_column(Text, nullable=False)

    expected_range_today: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expected_range_next_3d: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    danger_zone: Mapped[str] = mapped_column(Text, nullable=False)

    pin_risk: Mapped[str] = mapped_column(Text, nullable=False)
    event_risk: Mapped[str] = mapped_column(Text, nullable=False)
    iv_quality: Mapped[str] = mapped_column(Text, nullable=False)
    liquidity: Mapped[str] = mapped_column(Text, nullable=False)

    actual_dynamics_summary: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)

    # Audit-only blobs added in migration 0011. The flat columns above
    # remain the authoritative card body / decision; these are persisted
    # so each refresh's full Assessment Team + Decision Council debate
    # can be replayed without re-running the LLMs.
    assessment_layer: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    council_layer: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Explainability layer added in migration 0012. Versioned reasoning
    # payload that powers the "Open Full Report" Why? panels. Never
    # served by the card API — only via ``GET /dashboard/tickers/{ticker}/report``.
    explainability: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class TickerOptionOpportunityModel(Base):
    """Reverse-BWB combo opportunities (CALL/PUT), N rows per ticker.

    Refreshed via truncate-by-ticker + insert in ``DashboardRepository``. V1
    is a placeholder generator; V2 will be backed by an IBKR chain source.
    """

    __tablename__ = "ticker_option_opportunities"
    __table_args__ = (
        Index(
            "ix_ticker_option_opportunities_ticker_type_rank",
            "ticker",
            "option_type",
            "rank",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    ticker_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ticker_reports.id"), nullable=True
    )
    option_type: Mapped[str] = mapped_column(String(4), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    combo: Mapped[str] = mapped_column(Text, nullable=False)
    expiry: Mapped[str] = mapped_column(Text, nullable=False)
    premium: Mapped[float] = mapped_column(Float, nullable=False)
    margin: Mapped[float] = mapped_column(Float, nullable=False)
    liquidity: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class TickerMarketDataModel(Base):
    """Live IBKR-sourced quote, one row per watchlist ticker.

    Written continuously by the ``MarketDataWorker`` price loop; read by the
    new ``GET /api/v1/dashboard/live`` and ``/tickers/{t}/market-data``
    endpoints. Strictly separate from the analysis-snapshot tables —
    re-running analysis never touches this row, and a price tick never
    touches the analysis tables.
    """

    __tablename__ = "ticker_market_data"
    __table_args__ = (
        UniqueConstraint("ticker", name="uq_ticker_market_data_ticker"),
        Index("ix_ticker_market_data_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    change_abs: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    feed_status: Mapped[str] = mapped_column(Text, nullable=False, default="live")
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class TickerLiveOptionOpportunityModel(Base):
    """Live IBKR-sourced Reverse-BWB combo opportunities (CALL/PUT).

    Written by ``MarketDataWorker`` opportunity loop every ~30-60s (or when
    event-driven recalc fires). Refresh strategy: DELETE WHERE ticker=?
    AND side=? then INSERT — atomic per side so a partial refresh never
    strands stale rows.

    Schema extended in 0015 to support the full Reverse BWB Trading
    Workstation enumeration (per-leg OI/vol/IV, ranking_score, credit
    efficiency, opportunity_version, etc.). The legacy ``rank`` and
    ``spread_pct`` columns are retained for back-compat.
    """

    __tablename__ = "ticker_live_option_opportunities"
    __table_args__ = (
        Index(
            "ix_ticker_live_option_opportunities_ticker_side",
            "ticker",
            "side",
        ),
        Index(
            "ix_ticker_live_option_opportunities_version",
            "ticker",
            "opportunity_version",
        ),
        Index(
            "ix_ticker_live_option_opportunities_score",
            "ticker",
            text("ranking_score DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    combo: Mapped[str] = mapped_column(Text, nullable=False)
    strike_long_wing_a: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    strike_short_body: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    strike_long_wing_b: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    expiration: Mapped[str] = mapped_column(Text, nullable=False)
    expiry_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delta_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    # Sign-preserved (negative = credit, positive = debit) per-share value.
    premium: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    init_margin: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    maint_margin: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    init_margin_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="deterministic"
    )
    # Numeric liquidity (min of leg OI). Never a string in the new schema.
    liquidity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_open_interest: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oi_leg1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oi_leg2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oi_leg3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vol_leg1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vol_leg2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vol_leg3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iv_leg1: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    iv_leg2: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    iv_leg3: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    mid_leg1: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    mid_leg2: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    mid_leg3: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    credit_efficiency: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    ranking_score: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 6), nullable=True
    )
    underlying_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    iv: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    opportunity_version: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # Legacy fields preserved for back-compat — newer code uses
    # minimum_open_interest / minimum_volume.
    oi_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vol_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spread_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class TickerOptionOpportunityHistoryModel(Base):
    """Append-only archive of every generated Reverse-BWB opportunity.

    Written alongside ``ticker_live_option_opportunities`` on each
    event-driven recalc cycle. NEVER updated, NEVER deleted — this table
    is the foundation for backtesting, opportunity replay, best-X analyses,
    and future ML/LLM context enrichment.
    """

    __tablename__ = "ticker_option_opportunity_history"
    __table_args__ = (
        Index(
            "ix_ticker_option_opportunity_history_ticker_date",
            "ticker",
            "snapshot_date",
        ),
        Index(
            "ix_ticker_option_opportunity_history_ticker_gen_at",
            "ticker",
            "generated_at",
        ),
        Index(
            "ix_ticker_option_opportunity_history_version",
            "opportunity_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    combo: Mapped[str] = mapped_column(Text, nullable=False)
    strike_long_wing_a: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    strike_short_body: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    strike_long_wing_b: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    expiration: Mapped[str] = mapped_column(Text, nullable=False)
    expiry_days: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    premium: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    init_margin: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    maint_margin: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    init_margin_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="deterministic"
    )
    liquidity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_open_interest: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oi_leg1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oi_leg2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    oi_leg3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vol_leg1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vol_leg2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vol_leg3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iv_leg1: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    iv_leg2: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    iv_leg3: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    mid_leg1: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    mid_leg2: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    mid_leg3: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    credit_efficiency: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    ranking_score: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 6), nullable=True
    )
    underlying_price: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    iv: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    opportunity_version: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
    snapshot_date: Mapped[Any] = mapped_column(
        Date, server_default=text("CURRENT_DATE"), nullable=False
    )


class MarketCandle1mModel(Base):
    """1-minute OHLCV candles generated from live IBKR ticks.

    Written by ``MarketDataWorker._candle_flush_loop`` every ~60 s.
    Primary key is (ticker, ts) where ts is the UTC minute boundary.
    UPSERTs are safe — a late flush can update high/low/close/volume for
    a candle that was flushed while the minute was still open.
    """

    __tablename__ = "market_candles_1m"
    __table_args__ = (
        Index("ix_market_candles_1m_ticker_ts", "ticker", "ts"),
    )

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    open: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
