import asyncio

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.domains.health_metric.repository import HealthMetricRepository
from app.domains.onboarding.repository import OnboardingRepository
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.record.repository import RecordRepository
from app.domains.record.service import RecordService
from app.infrastructure.ocr.clova_client import ClovaOcrClient
from app.infrastructure.ocr.ocr_client import StubOcrClient
from app.infrastructure.ocr.parser import OcrParser

_ocr_capacity_limiter = asyncio.Semaphore(settings.ocr_global_concurrency)


def _build_ocr_client():
    if settings.clova_ocr_invoke_url and settings.clova_ocr_secret_key:
        return ClovaOcrClient(
            invoke_url=settings.clova_ocr_invoke_url,
            secret_key=settings.clova_ocr_secret_key,
            timeout=settings.ocr_request_timeout_seconds,
        )
    return StubOcrClient()


def build_ocr_service(db: Session) -> OcrService:
    return OcrService(
        ocr_repo=OcrRepository(db),
        record_repo=RecordRepository(db),
        ocr_client=_build_ocr_client(),
        parser=OcrParser(),
        max_retries=settings.ocr_max_retries,
        concurrency=settings.ocr_concurrency,
        global_limiter=_ocr_capacity_limiter,
        acquire_timeout_seconds=settings.ocr_acquire_timeout_seconds,
        retry_after_seconds=settings.ocr_retry_after_seconds,
    )


def get_ocr_service(db: Session = Depends(get_db)) -> OcrService:
    return build_ocr_service(db)


def get_record_service(db: Session = Depends(get_db)) -> RecordService:
    return RecordService(
        RecordRepository(db),
        OnboardingRepository(db),
        HealthMetricRepository(db),
    )
