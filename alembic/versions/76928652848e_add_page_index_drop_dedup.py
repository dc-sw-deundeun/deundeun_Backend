"""add_page_index_drop_dedup

Revision ID: 76928652848e
Revises: 983204074d73
Create Date: 2026-06-24 23:21:39.654928

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '76928652848e'
down_revision: Union[str, None] = '983204074d73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "checkup_metric_results",
        sa.Column("page_index", sa.Integer(), nullable=True),
    )
    # Only drop constraint if it exists (it may not exist due to prior migration failures)
    from sqlalchemy import inspect, text
    from sqlalchemy.engine import Engine

    inspector = inspect(op.get_bind())
    constraints = inspector.get_unique_constraints("checkup_records")
    constraint_names = [c["name"] for c in constraints]

    if "uq_checkup_records_user_file_hash" in constraint_names:
        op.drop_constraint(
            "uq_checkup_records_user_file_hash", "checkup_records", type_="unique"
        )


def downgrade() -> None:
    # Check if constraint already exists before creating
    from sqlalchemy import inspect

    inspector = inspect(op.get_bind())
    constraints = inspector.get_unique_constraints("checkup_records")
    constraint_names = [c["name"] for c in constraints]

    if "uq_checkup_records_user_file_hash" not in constraint_names:
        op.create_unique_constraint(
            "uq_checkup_records_user_file_hash",
            "checkup_records",
            ["user_id", "file_hash"],
        )
    op.drop_column("checkup_metric_results", "page_index")
