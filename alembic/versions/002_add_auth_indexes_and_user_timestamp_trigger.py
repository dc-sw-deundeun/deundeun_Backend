"""Add auth lookup indexes and users updated_at trigger

Revision ID: 002
Revises: 001
Create Date: 2026-06-24

"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_email_verifications_email_purpose_verified_at",
        "email_verifications",
        ["email", "purpose", "verified_at"],
    )
    op.create_index(
        "ix_refresh_tokens_user_id_revoked_at_expires_at",
        "refresh_tokens",
        ["user_id", "revoked_at", "expires_at"],
    )
    op.create_index(
        "ix_consent_histories_user_id_consent_type_agreed_at",
        "consent_histories",
        ["user_id", "consent_type", "agreed_at"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_users_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_users_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON users")
    op.execute("DROP FUNCTION IF EXISTS update_users_updated_at()")
    op.drop_index(
        "ix_consent_histories_user_id_consent_type_agreed_at",
        table_name="consent_histories",
    )
    op.drop_index(
        "ix_refresh_tokens_user_id_revoked_at_expires_at",
        table_name="refresh_tokens",
    )
    op.drop_index(
        "ix_email_verifications_email_purpose_verified_at",
        table_name="email_verifications",
    )
