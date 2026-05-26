"""Extend ticker_live_option_opportunities for the Workstation generator.

Revision ID: 0015_live_opportunities_extended
Revises: 0014_opportunity_history
Create Date: 2026-05-25

The original migration (0013) modelled the live table around the top-2-per-side
generator: it pinned ``UNIQUE(ticker, side, rank)`` so only a handful of rows
ever existed per ticker. The Workstation generator stores every valid
candidate, so:

    * The ``rank`` uniqueness constraint is dropped.
    * Numeric ``liquidity`` (min of leg OI) replaces the categorical text.
    * New columns capture strikes, delta %, per-leg OI/vol/IV/mid, margin
      source, credit efficiency, ranking score, IV, underlying snapshot,
      opportunity_version, expiry_days, and generated_at.
    * Indexes are added for the explorer endpoint's common sort keys.

Old rows survive (numeric ``liquidity`` defaults to 0 for the categorical
strings) and are overwritten by the next worker cycle.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_live_opportunities_extended"
down_revision: str | None = "0014_opportunity_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the unique constraint that capped rows per (ticker, side).
    op.drop_constraint(
        "uq_ticker_live_option_opportunities_ticker_side_rank",
        "ticker_live_option_opportunities",
        type_="unique",
    )

    # Convert categorical liquidity (text) -> numeric column.
    op.alter_column(
        "ticker_live_option_opportunities",
        "liquidity",
        existing_type=sa.Text(),
        type_=sa.Integer(),
        existing_nullable=False,
        nullable=False,
        server_default="0",
        postgresql_using="0",
    )

    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("strike_long_wing_a", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("strike_short_body", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("strike_long_wing_b", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("expiry_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("delta_pct", sa.Numeric(10, 4), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column(
            "init_margin_source",
            sa.String(16),
            nullable=False,
            server_default="deterministic",
        ),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("minimum_open_interest", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("minimum_volume", sa.Integer(), nullable=True),
    )
    for col in ("oi_leg1", "oi_leg2", "oi_leg3", "vol_leg1", "vol_leg2", "vol_leg3"):
        op.add_column(
            "ticker_live_option_opportunities",
            sa.Column(col, sa.Integer(), nullable=True),
        )
    for col in ("iv_leg1", "iv_leg2", "iv_leg3"):
        op.add_column(
            "ticker_live_option_opportunities",
            sa.Column(col, sa.Numeric(10, 6), nullable=True),
        )
    for col in ("mid_leg1", "mid_leg2", "mid_leg3"):
        op.add_column(
            "ticker_live_option_opportunities",
            sa.Column(col, sa.Numeric(14, 4), nullable=True),
        )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("credit_efficiency", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("ranking_score", sa.Numeric(14, 6), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("underlying_price", sa.Numeric(14, 4), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column("iv", sa.Numeric(10, 6), nullable=True),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column(
            "opportunity_version",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "ticker_live_option_opportunities",
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_ticker_live_option_opportunities_version",
        "ticker_live_option_opportunities",
        ["ticker", "opportunity_version"],
    )
    op.create_index(
        "ix_ticker_live_option_opportunities_score",
        "ticker_live_option_opportunities",
        ["ticker", sa.text("ranking_score DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticker_live_option_opportunities_score",
        table_name="ticker_live_option_opportunities",
    )
    op.drop_index(
        "ix_ticker_live_option_opportunities_version",
        table_name="ticker_live_option_opportunities",
    )
    for col in (
        "generated_at",
        "opportunity_version",
        "iv",
        "underlying_price",
        "ranking_score",
        "credit_efficiency",
        "mid_leg3",
        "mid_leg2",
        "mid_leg1",
        "iv_leg3",
        "iv_leg2",
        "iv_leg1",
        "vol_leg3",
        "vol_leg2",
        "vol_leg1",
        "oi_leg3",
        "oi_leg2",
        "oi_leg1",
        "minimum_volume",
        "minimum_open_interest",
        "init_margin_source",
        "delta_pct",
        "expiry_days",
        "strike_long_wing_b",
        "strike_short_body",
        "strike_long_wing_a",
    ):
        op.drop_column("ticker_live_option_opportunities", col)

    op.alter_column(
        "ticker_live_option_opportunities",
        "liquidity",
        existing_type=sa.Integer(),
        type_=sa.Text(),
        existing_nullable=False,
        nullable=False,
        server_default=None,
        postgresql_using="liquidity::text",
    )

    op.create_unique_constraint(
        "uq_ticker_live_option_opportunities_ticker_side_rank",
        "ticker_live_option_opportunities",
        ["ticker", "side", "rank"],
    )
