"""Add pkg_snapshots (PKG 영속을 Neo4j에서 Postgres로 이전)

Revision ID: 011
Revises: 010
Create Date: 2026-07-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pkg_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "built_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_record_id"], ["checkup_records.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_pkg_snapshots_user_id"),
    )
    op.create_index("ix_pkg_snapshots_user_id", "pkg_snapshots", ["user_id"])
    op.create_index("ix_pkg_snapshots_source_record_id", "pkg_snapshots", ["source_record_id"])


def downgrade() -> None:
    op.drop_table("pkg_snapshots")
