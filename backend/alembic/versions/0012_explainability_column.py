"""Explainability JSONB column on ticker_reverse_bwb_summary

Revision ID: 0012_explainability_column
Revises: 0011_assessment_council_columns
Create Date: 2026-05-25

Adds a single nullable JSONB column ``explainability`` to
``ticker_reverse_bwb_summary``. This column is the persisted form of the
``report_json.explainability`` versioned container that powers the "Open
Full Report" reasoning panels (credit-safety breakdown, confidence
calibration, liquidity assessment, structure analysis, position risk,
macro transmission, historical analogs, assessment reasoning, decision
justification).

Card contract impact: zero. The column is never returned by
``GET /api/v1/dashboard/tickers`` — only by the full-report endpoint.
Existing rows continue to validate because the column is nullable.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_explainability_column"
down_revision: str | None = "0011_assessment_council_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ticker_reverse_bwb_summary",
        sa.Column("explainability", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ticker_reverse_bwb_summary", "explainability")
