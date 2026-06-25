"""Add measured_at to health metric analyses

Revision ID: 005
Revises: 004
Create Date: 2026-06-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "health_metric_analyses",
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("health_metric_analyses", "measured_at")
