"""Reverse BWB Intelligence Dashboard tables

Revision ID: 0010_dashboard_tables
Revises: 0009_calibration_lineage
Create Date: 2026-05-24

Introduces three latest-per-ticker tables consumed by the watchlist grid:

    ticker_reports                — denormalized snapshot of latest research
                                    report per watchlist ticker (1:1 with
                                    ticker; upsert by ticker).
    ticker_reverse_bwb_summary    — LLM-synthesised Reverse BWB summary,
                                    1 row per ticker, upsert by ticker.
    ticker_option_opportunities   — placeholder CALL/PUT opportunities,
                                    N rows per ticker, truncate-by-ticker +
                                    insert on each refresh.

All three are additive — no existing tables are touched.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_dashboard_tables"
down_revision: str | None = "0009_calibration_lineage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticker_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
        ),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("research_report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="completed"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("report_json", postgresql.JSONB(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["research_report_id"], ["research_reports.id"]),
        sa.UniqueConstraint("ticker", name="uq_ticker_reports_ticker"),
    )
    op.create_index(
        "ix_ticker_reports_updated_at",
        "ticker_reports",
        ["updated_at"],
    )

    op.create_table(
        "ticker_reverse_bwb_summary",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
        ),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("ticker_report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("credit_safety_score", sa.Float(), nullable=False),
        sa.Column("risk", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=False),
        sa.Column("today_outlook", sa.Text(), nullable=False),
        sa.Column("next_3d_outlook", sa.Text(), nullable=False),
        sa.Column("chance_up_2_3_pct", sa.Text(), nullable=False),
        sa.Column("chance_down_2_3_pct", sa.Text(), nullable=False),
        sa.Column("expected_range_today", postgresql.JSONB(), nullable=False),
        sa.Column("expected_range_next_3d", postgresql.JSONB(), nullable=False),
        sa.Column("danger_zone", sa.Text(), nullable=False),
        sa.Column("pin_risk", sa.Text(), nullable=False),
        sa.Column("event_risk", sa.Text(), nullable=False),
        sa.Column("iv_quality", sa.Text(), nullable=False),
        sa.Column("liquidity", sa.Text(), nullable=False),
        sa.Column("actual_dynamics_summary", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["ticker_report_id"], ["ticker_reports.id"]),
        sa.UniqueConstraint("ticker", name="uq_ticker_reverse_bwb_summary_ticker"),
    )

    op.create_table(
        "ticker_option_opportunities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
        ),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("ticker_report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("option_type", sa.String(4), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("combo", sa.Text(), nullable=False),
        sa.Column("expiry", sa.Text(), nullable=False),
        sa.Column("premium", sa.Float(), nullable=False),
        sa.Column("margin", sa.Float(), nullable=False),
        sa.Column("liquidity", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["ticker_report_id"], ["ticker_reports.id"]),
    )
    op.create_index(
        "ix_ticker_option_opportunities_ticker_type_rank",
        "ticker_option_opportunities",
        ["ticker", "option_type", "rank"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ticker_option_opportunities_ticker_type_rank",
        table_name="ticker_option_opportunities",
    )
    op.drop_table("ticker_option_opportunities")
    op.drop_table("ticker_reverse_bwb_summary")
    op.drop_index("ix_ticker_reports_updated_at", table_name="ticker_reports")
    op.drop_table("ticker_reports")
