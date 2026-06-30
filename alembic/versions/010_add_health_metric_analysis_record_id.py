"""Add record link to health metric analyses

Revision ID: 010
Revises: 009
Create Date: 2026-06-30

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("health_metric_analyses", sa.Column("record_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_health_metric_analyses_record_id",
        "health_metric_analyses",
        ["record_id"],
    )
    op.create_foreign_key(
        "fk_health_metric_analyses_record_id_checkup_records",
        "health_metric_analyses",
        "checkup_records",
        ["record_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_health_metric_analyses_record_id_checkup_records",
        "health_metric_analyses",
        type_="foreignkey",
    )
    op.drop_index("ix_health_metric_analyses_record_id", table_name="health_metric_analyses")
    op.drop_column("health_metric_analyses", "record_id")
