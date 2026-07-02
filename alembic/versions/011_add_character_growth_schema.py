"""Add character growth schema

Revision ID: 011
Revises: 010
Create Date: 2026-06-30

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
        "character_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_exp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_character_profiles_user_id"),
    )
    op.create_index("ix_character_profiles_user_id", "character_profiles", ["user_id"])

    op.create_table(
        "character_growth_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_profile_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("exp_gained", sa.Integer(), nullable=False),
        sa.Column("before_level", sa.Integer(), nullable=False),
        sa.Column("after_level", sa.Integer(), nullable=False),
        sa.Column("before_total_exp", sa.Integer(), nullable=False),
        sa.Column("after_total_exp", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["character_profile_id"], ["character_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_character_growth_logs_character_profile_id",
        "character_growth_logs",
        ["character_profile_id"],
    )
    op.create_index("ix_character_growth_logs_user_id", "character_growth_logs", ["user_id"])

    op.create_table(
        "character_owned_animals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("character_profile_id", sa.Integer(), nullable=False),
        sa.Column("animal_code", sa.String(length=50), nullable=False),
        sa.Column("unlocked_level", sa.Integer(), nullable=False),
        sa.Column("unlocked_total_exp", sa.Integer(), nullable=False),
        sa.Column(
            "unlocked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["character_profile_id"], ["character_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "animal_code", name="uq_character_owned_animals_user_animal"
        ),
    )
    op.create_index(
        "ix_character_owned_animals_character_profile_id",
        "character_owned_animals",
        ["character_profile_id"],
    )
    op.create_index("ix_character_owned_animals_user_id", "character_owned_animals", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_character_owned_animals_user_id", table_name="character_owned_animals")
    op.drop_index(
        "ix_character_owned_animals_character_profile_id",
        table_name="character_owned_animals",
    )
    op.drop_table("character_owned_animals")
    op.drop_index("ix_character_growth_logs_user_id", table_name="character_growth_logs")
    op.drop_index(
        "ix_character_growth_logs_character_profile_id",
        table_name="character_growth_logs",
    )
    op.drop_table("character_growth_logs")
    op.drop_index("ix_character_profiles_user_id", table_name="character_profiles")
    op.drop_table("character_profiles")
