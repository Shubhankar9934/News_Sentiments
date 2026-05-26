"""Reverse BWB opportunity history archive (append-only).

Revision ID: 0014_opportunity_history
Revises: 0013_market_data_tables
Create Date: 2026-05-25

Adds the canonical append-only archive used by the Reverse BWB Trading
Workstation. Every event-driven recalc cycle (price > 0.25%, IV > 3%, 15-min
elapsed, or market open) writes the complete set of generated candidates to
both ``ticker_live_option_opportunities`` (current) and this table (history).

The history table is never UPDATEd or DELETEd. It is the foundation for:
    * Best-expiration / best-delta analysis
    * Backtesting and opportunity replay
    * Future ML / LLM context enrichment
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_opportunity_history"
down_revision: str | None = "0013_market_data_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticker_option_opportunity_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
        ),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("combo", sa.Text(), nullable=False),
        sa.Column("strike_long_wing_a", sa.Numeric(14, 4), nullable=False),
        sa.Column("strike_short_body", sa.Numeric(14, 4), nullable=False),
        sa.Column("strike_long_wing_b", sa.Numeric(14, 4), nullable=False),
        sa.Column("expiration", sa.Text(), nullable=False),
        sa.Column("expiry_days", sa.Integer(), nullable=False),
        sa.Column("delta_pct", sa.Numeric(10, 4), nullable=True),
        # Per-share premium. Negative => credit, positive => debit (raw, sign-preserved).
        sa.Column("premium", sa.Numeric(14, 4), nullable=False),
        sa.Column("init_margin", sa.Numeric(14, 2), nullable=True),
        sa.Column("maint_margin", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "init_margin_source",
            sa.String(16),
            nullable=False,
            server_default="deterministic",
        ),
        # Numeric liquidity = min(oi_leg1, oi_leg2, oi_leg3). Never a string.
        sa.Column("liquidity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minimum_open_interest", sa.Integer(), nullable=True),
        sa.Column("minimum_volume", sa.Integer(), nullable=True),
        sa.Column("oi_leg1", sa.Integer(), nullable=True),
        sa.Column("oi_leg2", sa.Integer(), nullable=True),
        sa.Column("oi_leg3", sa.Integer(), nullable=True),
        sa.Column("vol_leg1", sa.Integer(), nullable=True),
        sa.Column("vol_leg2", sa.Integer(), nullable=True),
        sa.Column("vol_leg3", sa.Integer(), nullable=True),
        sa.Column("iv_leg1", sa.Numeric(10, 6), nullable=True),
        sa.Column("iv_leg2", sa.Numeric(10, 6), nullable=True),
        sa.Column("iv_leg3", sa.Numeric(10, 6), nullable=True),
        sa.Column("mid_leg1", sa.Numeric(14, 4), nullable=True),
        sa.Column("mid_leg2", sa.Numeric(14, 4), nullable=True),
        sa.Column("mid_leg3", sa.Numeric(14, 4), nullable=True),
        sa.Column("credit_efficiency", sa.Numeric(14, 4), nullable=True),
        sa.Column("ranking_score", sa.Numeric(14, 6), nullable=True),
        sa.Column("underlying_price", sa.Numeric(14, 4), nullable=True),
        sa.Column("iv", sa.Numeric(10, 6), nullable=True),
        sa.Column(
            "opportunity_version",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_date",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ticker_option_opportunity_history_ticker_date",
        "ticker_option_opportunity_history",
        ["ticker", "snapshot_date"],
    )
    op.create_index(
        "ix_ticker_option_opportunity_history_ticker_gen_at",
        "ticker_option_opportunity_history",
        ["ticker", "generated_at"],
    )
    op.create_index(
        "ix_ticker_option_opportunity_history_version",
        "ticker_option_opportunity_history",
        ["opportunity_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticker_option_opportunity_history_version",
        table_name="ticker_option_opportunity_history",
    )
    op.drop_index(
        "ix_ticker_option_opportunity_history_ticker_gen_at",
        table_name="ticker_option_opportunity_history",
    )
    op.drop_index(
        "ix_ticker_option_opportunity_history_ticker_date",
        table_name="ticker_option_opportunity_history",
    )
    op.drop_table("ticker_option_opportunity_history")
