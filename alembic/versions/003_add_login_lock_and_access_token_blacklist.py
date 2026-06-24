"""Add login lock columns, users.token_version, and access_token_blacklist

Revision ID: 003
Revises: 002
Create Date: 2026-06-24

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users: 로그인 실패 잠금 + access token 일괄 무효화 ---
    op.add_column(
        "users",
        sa.Column("failed_login_count", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer, nullable=False, server_default="0"),
    )

    # --- access_token_blacklist: 로그아웃된 access token jti ---
    op.create_table(
        "access_token_blacklist",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_access_token_blacklist_expires_at",
        "access_token_blacklist",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_access_token_blacklist_expires_at",
        table_name="access_token_blacklist",
    )
    op.drop_table("access_token_blacklist")

    op.drop_column("users", "token_version")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
