"""Extend user_missions for engine-generated missions (인스턴스 저장)

Revision ID: 015
Revises: 014
Create Date: 2026-07-03

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_missions", sa.Column("template_code", sa.String(length=50), nullable=True))
    op.add_column("user_missions", sa.Column("payload", sa.JSON(), nullable=True))
    op.add_column("user_missions", sa.Column("completed_at", sa.DateTime(), nullable=True))
    # 엔진 생성 미션은 DB 템플릿이 없어 template_id가 null이다.
    op.alter_column("user_missions", "template_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("user_missions", "template_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("user_missions", "completed_at")
    op.drop_column("user_missions", "payload")
    op.drop_column("user_missions", "template_code")
