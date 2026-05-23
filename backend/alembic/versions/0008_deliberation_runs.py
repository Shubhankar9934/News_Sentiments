"""deliberation runs table

Revision ID: 0008_deliberation_runs
Revises: 0007_calibration_lineage
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_deliberation_runs"
down_revision: str | None = "0007_calibration_lineage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deliberation_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
        ),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("models_used", postgresql.JSONB(), nullable=True),
        sa.Column("layer_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["research_reports.id"]),
    )
    op.create_index("ix_deliberation_runs_report_id", "deliberation_runs", ["report_id"])


def downgrade() -> None:
    op.drop_index("ix_deliberation_runs_report_id", table_name="deliberation_runs")
    op.drop_table("deliberation_runs")
