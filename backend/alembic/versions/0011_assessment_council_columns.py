"""Assessment + Council audit columns on ticker_reverse_bwb_summary

Revision ID: 0011_assessment_council_columns
Revises: 0010_dashboard_tables
Create Date: 2026-05-24

Adds two additive JSONB columns to ``ticker_reverse_bwb_summary``:

    assessment_layer  — full Reverse BWB Assessment Team layer (3 LLMs,
                        4 rounds, deterministic consensus). Stored for
                        audit / replay; the flat summary columns
                        remain the authoritative card body.
    council_layer     — full Decision Council layer (5 LLMs, 4 rounds).
                        Stored for audit / replay; the flat ``decision``
                        column remains the authoritative trade verdict.

Both columns are nullable so existing rows continue to validate.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_assessment_council_columns"
down_revision: str | None = "0010_dashboard_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ticker_reverse_bwb_summary",
        sa.Column("assessment_layer", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "ticker_reverse_bwb_summary",
        sa.Column("council_layer", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ticker_reverse_bwb_summary", "council_layer")
    op.drop_column("ticker_reverse_bwb_summary", "assessment_layer")
