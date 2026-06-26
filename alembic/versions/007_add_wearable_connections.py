"""Add wearable connections (Phase 2 onboarding)

Revision ID: 007
Revises: 006
Create Date: 2026-06-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wearable_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.Enum(
                "APPLE_HEALTH",
                "SAMSUNG_HEALTH",
                "GOOGLE_FIT",
                name="wearable_provider_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "CONNECTED",
                "DISCONNECTED",
                "ERROR",
                name="wearable_status_enum",
            ),
            nullable=False,
        ),
        sa.Column("scopes", sa.JSON(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "provider", name="uq_wearable_connections_user_provider"
        ),
    )
    op.create_index(
        "ix_wearable_connections_user_id",
        "wearable_connections",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_wearable_connections_user_id",
        table_name="wearable_connections",
    )
    op.drop_table("wearable_connections")
    sa.Enum(name="wearable_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="wearable_provider_enum").drop(op.get_bind(), checkfirst=True)
