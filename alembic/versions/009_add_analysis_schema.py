"""Add analysis schema and default mission template seed

Revision ID: 009
Revises: 008
Create Date: 2026-06-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MISSION_TEMPLATE_SEED = [
    {
        "code": "DEFAULT_SELF_CHECK",
        "title": "오늘의 건강 체크",
        "description": "오늘 하루 건강 상태를 스스로 확인해 보세요.",
        "category": "HEALTH",
        "verification_mode": "SELF_CHECK",
        "default_xp": 10,
        "active": True,
    },
]


def upgrade() -> None:
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("external_job_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("raw_result", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_job_id"),
    )
    op.create_index("ix_analysis_jobs_record_id", "analysis_jobs", ["record_id"])
    op.create_index("ix_analysis_jobs_user_id", "analysis_jobs", ["user_id"])

    op.create_table(
        "checkup_analysis_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=30), nullable=False),
        sa.Column(
            "positive_points",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "caution_points",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "recommendations",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "avoidances",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("model_version", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_id"),
    )
    op.create_index(
        "ix_checkup_analysis_summaries_record_id",
        "checkup_analysis_summaries",
        ["record_id"],
    )
    op.create_index(
        "ix_checkup_analysis_summaries_job_id",
        "checkup_analysis_summaries",
        ["job_id"],
    )

    op.create_table(
        "analysis_mission_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("summary_id", sa.Integer(), nullable=False),
        sa.Column("candidate_type", sa.String(length=20), nullable=False),
        sa.Column("template_code", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("reason_code", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("verification_mode", sa.String(length=30), nullable=True),
        sa.Column("target_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_mission_candidates_summary_id",
        "analysis_mission_candidates",
        ["summary_id"],
    )

    op.create_table(
        "mission_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("verification_mode", sa.String(length=30), nullable=False),
        sa.Column("default_xp", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_mission_templates_code", "mission_templates", ["code"])

    op.create_table(
        "user_missions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("source_record_id", sa.Integer(), nullable=True),
        sa.Column("assigned_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ASSIGNED"),
        sa.Column("xp_reward", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "template_id",
            "assigned_date",
            name="uq_user_missions_user_template_date",
        ),
    )
    op.create_index("ix_user_missions_user_id", "user_missions", ["user_id"])
    op.create_index("ix_user_missions_template_id", "user_missions", ["template_id"])
    op.create_index("ix_user_missions_source_record_id", "user_missions", ["source_record_id"])

    mission_templates = sa.table(
        "mission_templates",
        sa.column("code", sa.String),
        sa.column("title", sa.String),
        sa.column("description", sa.Text),
        sa.column("category", sa.String),
        sa.column("verification_mode", sa.String),
        sa.column("default_xp", sa.Integer),
        sa.column("active", sa.Boolean),
    )
    op.bulk_insert(mission_templates, MISSION_TEMPLATE_SEED)


def downgrade() -> None:
    op.drop_table("user_missions")
    op.drop_table("mission_templates")
    op.drop_table("analysis_mission_candidates")
    op.drop_table("checkup_analysis_summaries")
    op.drop_table("analysis_jobs")
