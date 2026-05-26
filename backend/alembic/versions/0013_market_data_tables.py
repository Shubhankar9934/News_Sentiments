"""Live IBKR market-data tables

Revision ID: 0013_market_data_tables
Revises: 0012_explainability_column
Create Date: 2026-05-25

Adds two new tables consumed by the live IBKR feed (Phase 1-7 of the
"IBKR Live Market Data Integration" plan):

    ticker_market_data                 — one live quote per watchlist ticker;
                                         UPSERT keyed by (ticker). Written
                                         continuously by ``MarketDataWorker``
                                         price loop.
    ticker_live_option_opportunities   — top live Reverse-BWB combos per
                                         ticker x side; refresh strategy is
                                         DELETE WHERE ticker=? AND side=?
                                         then INSERT. Written every ~45s by
                                         ``MarketDataWorker`` opportunity
                                         loop.

Both tables are strictly additive — no existing analysis-snapshot table is
touched. The existing ``ticker_option_opportunities`` table is left in
place for backward compatibility but is no longer rendered when the live
feed is enabled.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_market_data_tables"
down_revision: str | None = "0012_explainability_column"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticker_market_data",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
        ),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("last_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("bid", sa.Numeric(14, 4), nullable=True),
        sa.Column("ask", sa.Numeric(14, 4), nullable=True),
        sa.Column("change_abs", sa.Numeric(14, 4), nullable=True),
        sa.Column("change_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("prev_close", sa.Numeric(14, 4), nullable=True),
        sa.Column(
            "feed_status",
            sa.Text(),
            nullable=False,
            server_default="live",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.UniqueConstraint("ticker", name="uq_ticker_market_data_ticker"),
    )
    op.create_index(
        "ix_ticker_market_data_updated_at",
        "ticker_market_data",
        ["updated_at"],
    )

    op.create_table(
        "ticker_live_option_opportunities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
        ),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("combo", sa.Text(), nullable=False),
        sa.Column("expiration", sa.Text(), nullable=False),
        sa.Column("premium", sa.Numeric(14, 4), nullable=False),
        sa.Column("init_margin", sa.Numeric(14, 2), nullable=True),
        sa.Column("maint_margin", sa.Numeric(14, 2), nullable=True),
        sa.Column("liquidity", sa.Text(), nullable=False),
        sa.Column("oi_min", sa.Integer(), nullable=True),
        sa.Column("vol_min", sa.Integer(), nullable=True),
        sa.Column("spread_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "ticker",
            "side",
            "rank",
            name="uq_ticker_live_option_opportunities_ticker_side_rank",
        ),
    )
    op.create_index(
        "ix_ticker_live_option_opportunities_ticker_side",
        "ticker_live_option_opportunities",
        ["ticker", "side"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticker_live_option_opportunities_ticker_side",
        table_name="ticker_live_option_opportunities",
    )
    op.drop_table("ticker_live_option_opportunities")
    op.drop_index(
        "ix_ticker_market_data_updated_at",
        table_name="ticker_market_data",
    )
    op.drop_table("ticker_market_data")
