from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.health_metric.models import HealthMetricAnalysis


class HealthMetricRepository:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def find_by_metric_code(self, metric_code: str):
        raise NotImplementedError

    def find_all(self):
        raise NotImplementedError

    def save(self, reference) -> None:
        raise NotImplementedError


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
