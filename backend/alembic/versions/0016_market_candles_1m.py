"""Add market_candles_1m table for 1-minute OHLCV tick aggregation.

Revision ID: 0016_market_candles_1m
Revises: 0015_live_opportunities_extended
Create Date: 2026-05-26

Written by ``MarketDataWorker._candle_flush_loop`` every ~60 s.
Primary key (ticker, ts) with ts as the UTC minute boundary.
Supports UPSERT (ON CONFLICT DO UPDATE) so a late flush can safely
update high/low/close/volume for a candle that was partially written.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016_market_candles_1m"
down_revision = "0015_live_opportunities_extended"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_candles_1m",
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(14, 4), nullable=True),
        sa.Column("high", sa.Numeric(14, 4), nullable=True),
        sa.Column("low", sa.Numeric(14, 4), nullable=True),
        sa.Column("close", sa.Numeric(14, 4), nullable=True),
        sa.Column("volume", sa.BigInteger, nullable=True),
        sa.PrimaryKeyConstraint("ticker", "ts", name="pk_market_candles_1m"),
    )
    op.create_index(
        "ix_market_candles_1m_ticker_ts",
        "market_candles_1m",
        ["ticker", "ts"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_candles_1m_ticker_ts", table_name="market_candles_1m")
    op.drop_table("market_candles_1m")
