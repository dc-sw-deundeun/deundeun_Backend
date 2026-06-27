"""Add health_metric_references and restore checkup file_hash dedup

Revision ID: 008
Revises: 007
Create Date: 2026-06-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

from app.domains.health_metric.reference_seed import REFERENCE_SEED

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "health_metric_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric_code", sa.String(length=50), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_min", sa.Float(), nullable=True),
        sa.Column("reference_max", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.UniqueConstraint("metric_code", name="uq_health_metric_references_metric_code"),
    )
    op.bulk_insert(
        sa.table(
            "health_metric_references",
            sa.column("metric_code", sa.String),
            sa.column("metric_name", sa.String),
            sa.column("description", sa.Text),
            sa.column("reference_min", sa.Float),
            sa.column("reference_max", sa.Float),
            sa.column("unit", sa.String),
        ),
        REFERENCE_SEED,
    )
    op.create_index(
        "uq_checkup_records_user_file_hash",
        "checkup_records",
        ["user_id", "file_hash"],
        unique=True,
        postgresql_where=sa.text("file_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_checkup_records_user_file_hash", table_name="checkup_records")
    op.drop_table("health_metric_references")
