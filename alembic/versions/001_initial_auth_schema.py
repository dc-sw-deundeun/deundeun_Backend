"""Initial auth schema: users, email_verifications, refresh_tokens, consent_histories

Revision ID: 001
Revises:
Create Date: 2026-06-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Enum types ---
    user_status_enum = postgresql.ENUM(
        "ACTIVE", "SUSPENDED", "DELETED", name="user_status_enum", create_type=False
    )
    onboarding_step_enum = postgresql.ENUM(
        "CONSENT",
        "WEARABLE",
        "INITIAL_CHECKUP",
        "CHECKUP_VERIFIED",
        "COMPLETED",
        name="onboarding_step_enum",
        create_type=False,
    )
    verification_purpose_enum = postgresql.ENUM(
        "SIGNUP", "PASSWORD_RESET", name="verification_purpose_enum", create_type=False
    )
    consent_type_enum = postgresql.ENUM(
        "TERMS_OF_SERVICE", "PRIVACY", "HEALTH_DATA", name="consent_type_enum", create_type=False
    )

    user_status_enum.create(op.get_bind(), checkfirst=True)
    onboarding_step_enum.create(op.get_bind(), checkfirst=True)
    verification_purpose_enum.create(op.get_bind(), checkfirst=True)
    consent_type_enum.create(op.get_bind(), checkfirst=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("nickname", sa.String(50), nullable=False),
        sa.Column(
            "onboarding_step", onboarding_step_enum, nullable=False, server_default="CONSENT"
        ),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Seoul"),
        sa.Column("status", user_status_enum, nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- email_verifications ---
    op.create_table(
        "email_verifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("purpose", verification_purpose_enum, nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_email_verifications_email", "email_verifications", ["email"])

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(255), nullable=False, unique=True),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # --- consent_histories ---
    op.create_table(
        "consent_histories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("consent_type", consent_type_enum, nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("agreed", sa.Boolean, nullable=False),
        sa.Column(
            "agreed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_consent_histories_user_id", "consent_histories", ["user_id"])


def downgrade() -> None:
    op.drop_table("consent_histories")
    op.drop_table("refresh_tokens")
    op.drop_table("email_verifications")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS consent_type_enum")
    op.execute("DROP TYPE IF EXISTS verification_purpose_enum")
    op.execute("DROP TYPE IF EXISTS onboarding_step_enum")
    op.execute("DROP TYPE IF EXISTS user_status_enum")
