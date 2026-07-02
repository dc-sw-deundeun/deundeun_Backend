from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.health_metric.models import HealthMetricAnalysis, HealthMetricReference


class HealthMetricRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_metric_code(self, metric_code: str) -> HealthMetricReference | None:
        return self.db.scalar(
            select(HealthMetricReference).where(HealthMetricReference.metric_code == metric_code)
        )

    def find_all(self) -> list[HealthMetricReference]:
        return list(
            self.db.scalars(select(HealthMetricReference).order_by(HealthMetricReference.id))
        )

    def save(self, reference: HealthMetricReference) -> HealthMetricReference:
        self.db.add(reference)
        self.db.flush()
        return reference


class HealthMetricAnalysisRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, analysis: HealthMetricAnalysis) -> HealthMetricAnalysis:
        self.db.add(analysis)
        self.db.flush()
        return analysis

    def get(self, analysis_id: int) -> HealthMetricAnalysis | None:
        return self.db.scalar(
            select(HealthMetricAnalysis).where(HealthMetricAnalysis.id == analysis_id)
        )

    def get_for_user(self, analysis_id: int, user_id: int) -> HealthMetricAnalysis | None:
        return self.db.scalar(
            select(HealthMetricAnalysis).where(
                HealthMetricAnalysis.id == analysis_id,
                HealthMetricAnalysis.user_id == user_id,
            )
        )

    def get_latest_for_record(self, record_id: int, user_id: int) -> HealthMetricAnalysis | None:
        return self.db.scalar(
            select(HealthMetricAnalysis)
            .where(
                HealthMetricAnalysis.record_id == record_id,
                HealthMetricAnalysis.user_id == user_id,
            )
            .order_by(HealthMetricAnalysis.created_at.desc(), HealthMetricAnalysis.id.desc())
            .limit(1)
        )

    def list_for_user(self, user_id: int) -> list[HealthMetricAnalysis]:
        return list(
            self.db.scalars(
                select(HealthMetricAnalysis)
                .where(HealthMetricAnalysis.user_id == user_id)
                .order_by(HealthMetricAnalysis.created_at.asc(), HealthMetricAnalysis.id.asc())
            )
        )
