"""Add health metric analyses

Revision ID: 004
Revises: 003
Create Date: 2026-06-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "health_metric_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sex", sa.String(length=20), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("results_payload", sa.JSON(), nullable=False),
        sa.Column("explanation_payload", sa.JSON(), nullable=False),
        sa.Column("summary_payload", sa.JSON(), nullable=False),
        sa.Column("details_payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_health_metric_analyses_user_id",
        "health_metric_analyses",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_health_metric_analyses_user_id",
        table_name="health_metric_analyses",
    )
    op.drop_table("health_metric_analyses")
