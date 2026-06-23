"""drop ocr_jobs.raw_result_url

Revision ID: 983204074d73
Revises: 97a644712a37
Create Date: 2026-06-23 22:11:01.029397

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '983204074d73'
down_revision: Union[str, None] = '97a644712a37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("ocr_jobs", "raw_result_url")


def downgrade() -> None:
    op.add_column(
        "ocr_jobs",
        sa.Column("raw_result_url", sa.String(length=500), nullable=True),
    )
