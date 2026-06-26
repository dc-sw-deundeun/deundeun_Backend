"""Merge health metric and OCR migration heads

Revision ID: 006
Revises: 005, 76928652848e
Create Date: 2026-06-26

"""

from collections.abc import Sequence

revision: str = "006"
down_revision: tuple[str, str] = ("005", "76928652848e")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
