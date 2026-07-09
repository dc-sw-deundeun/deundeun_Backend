"""add user sex

Revision ID: 020
Revises: 019
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    user_sex_enum = sa.Enum("MALE", "FEMALE", name="user_sex_enum")
    user_sex_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "sex",
            user_sex_enum,
            server_default="MALE",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "sex")
    sa.Enum(name="user_sex_enum").drop(op.get_bind(), checkfirst=True)
