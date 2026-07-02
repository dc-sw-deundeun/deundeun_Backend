"""Normalize health metric analysis results

Revision ID: 011
Revises: 010
Create Date: 2026-07-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "health_metric_analyses",
        sa.Column("overall_title", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "health_metric_analyses",
        sa.Column("overall_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "health_metric_analyses",
        sa.Column("normal_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "health_metric_analyses",
        sa.Column("caution_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "health_metric_analyses",
        sa.Column("risk_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "health_metric_analyses",
        sa.Column("unknown_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "health_metric_analyses",
        sa.Column("explanation_status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "health_metric_analyses",
        sa.Column("disclaimer", sa.Text(), nullable=True),
    )
    op.alter_column("health_metric_analyses", "request_payload", nullable=True)
    op.alter_column("health_metric_analyses", "results_payload", nullable=True)
    op.alter_column("health_metric_analyses", "explanation_payload", nullable=True)
    op.alter_column("health_metric_analyses", "summary_payload", nullable=True)
    op.alter_column("health_metric_analyses", "details_payload", nullable=True)
    op.create_index(
        "ix_health_metric_analyses_user_created_at",
        "health_metric_analyses",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_health_metric_analyses_user_measured_at",
        "health_metric_analyses",
        ["user_id", "measured_at"],
    )

    op.create_table(
        "health_metric_analysis_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("health_metric_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_metric_code", sa.String(length=50), nullable=False),
        sa.Column("input_metric_name", sa.String(length=100), nullable=False),
        sa.Column("canonical_test_code", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("raw_text", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("status_label", sa.String(length=20), nullable=False),
        sa.Column("matched_rule", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("explanation_title", sa.String(length=100), nullable=False),
        sa.Column("explanation_body", sa.Text(), nullable=False),
        sa.Column("value_text", sa.String(length=50), nullable=False),
        sa.Column("badge_text", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_hmai_analysis_sort", "health_metric_analysis_items", ["analysis_id", "sort_order"]
    )
    op.create_index(
        "ix_hmai_code_value", "health_metric_analysis_items", ["canonical_test_code", "value"]
    )
    op.create_index("ix_hmai_status", "health_metric_analysis_items", ["status"])

    op.create_table(
        "health_metric_analysis_item_ranges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("health_metric_analysis_items.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("range_min", sa.Numeric(12, 4), nullable=False),
        sa.Column("range_max", sa.Numeric(12, 4), nullable=False),
        sa.Column("marker", sa.Numeric(12, 4), nullable=False),
        sa.Column("marker_percent", sa.Numeric(6, 2), nullable=False),
        sa.Column("active_label", sa.String(length=100), nullable=True),
        sa.Column("active_from_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("active_to_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("active_color", sa.String(length=20), nullable=True),
        sa.Column("active_marker_percent", sa.Numeric(6, 2), nullable=True),
    )
    op.create_index("ix_hmair_item_id", "health_metric_analysis_item_ranges", ["item_id"])

    op.create_table(
        "health_metric_analysis_range_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("health_metric_analysis_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("from_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("to_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("item_id", "sort_order", name="uq_hmars_item_sort_order"),
    )
    op.create_index("ix_hmars_item_id", "health_metric_analysis_range_segments", ["item_id"])

    op.create_table(
        "health_metric_analysis_item_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("health_metric_analysis_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=100),
            server_default="맞춤 추천 습관",
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("item_id", "sort_order", name="uq_hmair_item_sort_order"),
    )
    op.create_index(
        "ix_hmair_recommendations_item_id",
        "health_metric_analysis_item_recommendations",
        ["item_id"],
    )

    op.create_table(
        "health_metric_analysis_highlights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("health_metric_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("analysis_id", "sort_order", name="uq_hmah_analysis_sort_order"),
    )
    op.create_index("ix_hmah_analysis_id", "health_metric_analysis_highlights", ["analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_hmah_analysis_id", table_name="health_metric_analysis_highlights")
    op.drop_table("health_metric_analysis_highlights")
    op.drop_index(
        "ix_hmair_recommendations_item_id",
        table_name="health_metric_analysis_item_recommendations",
    )
    op.drop_table("health_metric_analysis_item_recommendations")
    op.drop_index("ix_hmars_item_id", table_name="health_metric_analysis_range_segments")
    op.drop_table("health_metric_analysis_range_segments")
    op.drop_index("ix_hmair_item_id", table_name="health_metric_analysis_item_ranges")
    op.drop_table("health_metric_analysis_item_ranges")
    op.drop_index("ix_hmai_status", table_name="health_metric_analysis_items")
    op.drop_index("ix_hmai_code_value", table_name="health_metric_analysis_items")
    op.drop_index("ix_hmai_analysis_sort", table_name="health_metric_analysis_items")
    op.drop_table("health_metric_analysis_items")
    op.drop_index("ix_health_metric_analyses_user_measured_at", table_name="health_metric_analyses")
    op.drop_index("ix_health_metric_analyses_user_created_at", table_name="health_metric_analyses")
    op.alter_column("health_metric_analyses", "details_payload", nullable=False)
    op.alter_column("health_metric_analyses", "summary_payload", nullable=False)
    op.alter_column("health_metric_analyses", "explanation_payload", nullable=False)
    op.alter_column("health_metric_analyses", "results_payload", nullable=False)
    op.alter_column("health_metric_analyses", "request_payload", nullable=False)
    op.drop_column("health_metric_analyses", "disclaimer")
    op.drop_column("health_metric_analyses", "explanation_status")
    op.drop_column("health_metric_analyses", "unknown_count")
    op.drop_column("health_metric_analyses", "risk_count")
    op.drop_column("health_metric_analyses", "caution_count")
    op.drop_column("health_metric_analyses", "normal_count")
    op.drop_column("health_metric_analyses", "overall_summary")
    op.drop_column("health_metric_analyses", "overall_title")
