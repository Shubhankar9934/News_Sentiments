"""ORM models aligned with legacy PostgreSQL schema."""

import uuid
from datetime import datetime
from typing import Any

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
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
