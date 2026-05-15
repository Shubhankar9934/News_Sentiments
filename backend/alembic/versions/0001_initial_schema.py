"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.create_table(
        "raw_articles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_table(
        "processed_articles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("raw_article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("sentiment_label", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=True),
        sa.Column("reliability_score", sa.Integer(), nullable=True),
        sa.Column("impact_score", sa.Float(), nullable=True),
        sa.Column("abnormal_return", sa.Float(), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=True),
        sa.Column("cluster_id", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.ForeignKeyConstraint(["raw_article_id"], ["raw_articles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_processed_ticker_date",
        "processed_articles",
        ["ticker", "published_at"],
        unique=False,
        postgresql_ops={"published_at": "DESC"},
    )
    op.create_table(
        "ohlcv_bars",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timeframe", sa.Text(), server_default=sa.text("'1d'"), nullable=True),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "timestamp", "timeframe", name="uq_ohlcv_ticker_ts_tf"),
    )
    op.create_index(
        "idx_ohlcv_ticker_ts",
        "ohlcv_bars",
        ["ticker", "timestamp"],
        unique=False,
        postgresql_ops={"timestamp": "DESC"},
    )
    op.create_table(
        "research_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("time_window", sa.Text(), nullable=True),
        sa.Column("report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_mode", sa.Text(), nullable=True),
        sa.Column("articles_ct", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_reports_ticker",
        "research_reports",
        ["ticker", "created_at"],
        unique=False,
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_reports_ticker", table_name="research_reports")
    op.drop_table("research_reports")
    op.drop_index("idx_ohlcv_ticker_ts", table_name="ohlcv_bars")
    op.drop_table("ohlcv_bars")
    op.drop_index("idx_processed_ticker_date", table_name="processed_articles")
    op.drop_table("processed_articles")
    op.drop_table("raw_articles")
