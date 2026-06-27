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
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def get(self, analysis_id: int) -> HealthMetricAnalysis | None:
        return self.db.scalar(
            select(HealthMetricAnalysis).where(HealthMetricAnalysis.id == analysis_id)
        )
