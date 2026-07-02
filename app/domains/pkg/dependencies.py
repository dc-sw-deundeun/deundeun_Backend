from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.domains.analysis.repository import AnalysisRepository
from app.domains.health_metric.repository import HealthMetricAnalysisRepository
from app.domains.pkg.repository import PkgRepository
from app.domains.pkg.service import PkgService
from app.domains.record.repository import RecordRepository


def get_pkg_service(db: Session = Depends(get_db)) -> PkgService:
    return PkgService(
        RecordRepository(db),
        AnalysisRepository(db),
        HealthMetricAnalysisRepository(db),
        PkgRepository(db),
    )
