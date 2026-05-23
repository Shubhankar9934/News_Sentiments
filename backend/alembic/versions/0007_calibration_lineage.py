"""calibration lineage compatibility revision

Revision ID: 0007_calibration_lineage
Revises: 0001_initial
Create Date: 2026-05-18
"""

from collections.abc import Sequence

revision: str = "0007_calibration_lineage"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Compatibility migration: the checked-in schema already matches the current metadata.
    pass


def downgrade() -> None:
    pass