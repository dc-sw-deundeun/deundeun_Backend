"""add location consent

Revision ID: 019
Revises: 018
Create Date: 2026-07-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE consent_type_enum ADD VALUE IF NOT EXISTS 'LOCATION'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be dropped safely without rebuilding the type.
    pass
