"""calibration lineage columns on deliberation_runs

Revision ID: 0009_calibration_lineage
Revises: 0008_deliberation_runs
Create Date: 2026-05-22

Adds nullable lineage columns to ``deliberation_runs`` so future
calibration / outcome-tracking work can compare published verdicts against
realised market outcomes. The fields are populated from each consensus
synthesis at completion time; outcome-tracking columns stay NULL until a
follow-up job ingests realised returns.

No data backfill is required — every column is nullable.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_calibration_lineage"
down_revision: str | None = "0008_deliberation_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CALIBRATION_COLUMNS = (
    ("consensus_stance", sa.Text(), True),
    ("reconciled_label", sa.Text(), True),
    ("consensus_confidence", sa.Numeric(4, 3), True),
    ("directional_conviction", sa.Numeric(4, 3), True),
    ("consensus_strength", sa.Numeric(4, 3), True),
    ("agreement_score", sa.Numeric(4, 3), True),
    ("divergence", sa.Numeric(4, 3), True),
    ("contradiction_density", sa.Numeric(4, 3), True),
    ("uncertainty", sa.Text(), True),
    ("primary_risks", postgresql.JSONB(), True),
    ("outcome_window_end", sa.DateTime(timezone=True), True),
    ("realized_return", sa.Numeric(), True),
    ("outcome_label", sa.Text(), True),
    ("calibration_score", sa.Numeric(), True),
)


def upgrade() -> None:
    for name, col_type, nullable in _CALIBRATION_COLUMNS:
        op.add_column(
            "deliberation_runs",
            sa.Column(name, col_type, nullable=nullable),
        )
    op.create_index(
        "ix_deliberation_runs_calibration_outcome",
        "deliberation_runs",
        ["consensus_stance", "outcome_window_end"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deliberation_runs_calibration_outcome",
        table_name="deliberation_runs",
    )
    for name, _, _ in _CALIBRATION_COLUMNS:
        op.drop_column("deliberation_runs", name)
