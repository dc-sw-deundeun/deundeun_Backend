from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.domains.analysis.repository import AnalysisRepository
from app.domains.analysis.service import AnalysisService
from app.domains.mission.repository import MissionRepository
from app.domains.onboarding.repository import OnboardingRepository
from app.domains.record.repository import RecordRepository
from app.infrastructure.external_analysis.analysis_client import StubAnalysisClient


def _build_analysis_client() -> StubAnalysisClient:
    if settings.analysis_client == "stub":
        return StubAnalysisClient()
    if settings.analysis_client in {"http", "openai"}:
        raise NotImplementedError(
            f"Analysis client '{settings.analysis_client}' is not implemented yet."
        )
    raise ValueError(f"Unsupported analysis client: {settings.analysis_client}")


def build_analysis_service(db: Session) -> AnalysisService:
    return AnalysisService(
        analysis_repo=AnalysisRepository(db),
        record_repo=RecordRepository(db),
        mission_repo=MissionRepository(db),
        onboarding_repo=OnboardingRepository(db),
        analysis_client=_build_analysis_client(),
    )


def get_analysis_service(db: Session = Depends(get_db)) -> AnalysisService:
    return build_analysis_service(db)
