"""Add health_metric_references and restore checkup file_hash dedup

Revision ID: 008
Revises: 007
Create Date: 2026-06-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

REFERENCE_SEED: list[dict] = [
    {
        "metric_code": "height",
        "metric_name": "신장",
        "description": "키",
        "reference_min": None,
        "reference_max": None,
        "unit": "cm",
    },
    {
        "metric_code": "weight",
        "metric_name": "체중",
        "description": "몸무게",
        "reference_min": None,
        "reference_max": None,
        "unit": "kg",
    },
    {
        "metric_code": "waist",
        "metric_name": "허리둘레",
        "description": "복부 비만 지표",
        "reference_min": None,
        "reference_max": None,
        "unit": "cm",
    },
    {
        "metric_code": "bmi",
        "metric_name": "체질량지수",
        "description": "체중과 신장으로 계산한 비만 지표",
        "reference_min": 18.5,
        "reference_max": 24.9,
        "unit": "kg/m2",
    },
    {
        "metric_code": "blood_pressure",
        "metric_name": "혈압",
        "description": "수축기·이완기 혈압",
        "reference_min": None,
        "reference_max": None,
        "unit": "mmHg",
    },
    {
        "metric_code": "systolic_bp",
        "metric_name": "수축기혈압",
        "description": "최고 혈압",
        "reference_min": None,
        "reference_max": 119.0,
        "unit": "mmHg",
    },
    {
        "metric_code": "diastolic_bp",
        "metric_name": "이완기혈압",
        "description": "최저 혈압",
        "reference_min": None,
        "reference_max": 79.0,
        "unit": "mmHg",
    },
    {
        "metric_code": "fasting_glucose",
        "metric_name": "공복혈당",
        "description": "공복 시 혈당",
        "reference_min": None,
        "reference_max": 99.0,
        "unit": "mg/dL",
    },
    {
        "metric_code": "urine_protein",
        "metric_name": "요단백",
        "description": "소변 단백 검사",
        "reference_min": None,
        "reference_max": None,
        "unit": "",
    },
    {
        "metric_code": "creatinine",
        "metric_name": "혈청크레아티닌",
        "description": "신장 기능 지표",
        "reference_min": None,
        "reference_max": 1.5,
        "unit": "mg/dL",
    },
    {
        "metric_code": "egfr",
        "metric_name": "신사구체여과율",
        "description": "신장 여과 기능",
        "reference_min": 60.0,
        "reference_max": None,
        "unit": "mL/min",
    },
    {
        "metric_code": "hemoglobin",
        "metric_name": "혈색소",
        "description": "빈혈·철분 상태 지표",
        "reference_min": 12.0,
        "reference_max": 16.5,
        "unit": "g/dL",
    },
    {
        "metric_code": "ast",
        "metric_name": "AST",
        "description": "간 기능 지표",
        "reference_min": None,
        "reference_max": 40.0,
        "unit": "U/L",
    },
    {
        "metric_code": "alt",
        "metric_name": "ALT",
        "description": "간 기능 지표",
        "reference_min": None,
        "reference_max": 35.0,
        "unit": "U/L",
    },
    {
        "metric_code": "gamma_gtp",
        "metric_name": "감마지티피",
        "description": "간·담도 기능 지표",
        "reference_min": None,
        "reference_max": 63.0,
        "unit": "U/L",
    },
    {
        "metric_code": "total_cholesterol",
        "metric_name": "총콜레스테롤",
        "description": "혈중 콜레스테롤",
        "reference_min": None,
        "reference_max": 199.0,
        "unit": "mg/dL",
    },
    {
        "metric_code": "hdl",
        "metric_name": "HDL콜레스테롤",
        "description": "좋은 콜레스테롤",
        "reference_min": 40.0,
        "reference_max": None,
        "unit": "mg/dL",
    },
    {
        "metric_code": "ldl",
        "metric_name": "LDL콜레스테롤",
        "description": "나쁜 콜레스테롤",
        "reference_min": None,
        "reference_max": 129.0,
        "unit": "mg/dL",
    },
    {
        "metric_code": "triglyceride",
        "metric_name": "트리글리세라이드",
        "description": "중성지방",
        "reference_min": None,
        "reference_max": 149.0,
        "unit": "mg/dL",
    },
]

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TEMPORARY TABLE tmp_duplicate_checkup_records ON COMMIT DROP AS
            SELECT id
            FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY user_id, file_hash
                        ORDER BY created_at ASC, id ASC
                    ) AS row_num
                FROM checkup_records
                WHERE file_hash IS NOT NULL
            ) ranked
            WHERE row_num > 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM checkup_metric_results
            WHERE record_id IN (SELECT id FROM tmp_duplicate_checkup_records)
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM ocr_jobs
            WHERE record_id IN (SELECT id FROM tmp_duplicate_checkup_records)
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM checkup_records
            WHERE id IN (SELECT id FROM tmp_duplicate_checkup_records)
            """
        )
    )
    op.create_table(
        "health_metric_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric_code", sa.String(length=50), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_min", sa.Float(), nullable=True),
        sa.Column("reference_max", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.UniqueConstraint("metric_code", name="uq_health_metric_references_metric_code"),
    )
    op.bulk_insert(
        sa.table(
            "health_metric_references",
            sa.column("metric_code", sa.String),
            sa.column("metric_name", sa.String),
            sa.column("description", sa.Text),
            sa.column("reference_min", sa.Float),
            sa.column("reference_max", sa.Float),
            sa.column("unit", sa.String),
        ),
        REFERENCE_SEED,
    )
    op.create_index(
        "uq_checkup_records_user_file_hash",
        "checkup_records",
        ["user_id", "file_hash"],
        unique=True,
        postgresql_where=sa.text("file_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_checkup_records_user_file_hash", table_name="checkup_records")
    op.drop_table("health_metric_references")
