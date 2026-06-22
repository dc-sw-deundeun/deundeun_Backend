from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.record.repository import RecordRepository
from app.domains.record.service import RecordService
from app.infrastructure.ocr.clova_client import ClovaOcrClient
from app.infrastructure.ocr.ocr_client import StubOcrClient
from app.infrastructure.ocr.parser import OcrParser
from app.infrastructure.storage.file_storage import StubFileStorage


def _build_ocr_client():
    if settings.clova_ocr_invoke_url and settings.clova_ocr_secret_key:
        return ClovaOcrClient(
            invoke_url=settings.clova_ocr_invoke_url,
            secret_key=settings.clova_ocr_secret_key,
            timeout=settings.ocr_request_timeout_seconds,
        )
    return StubOcrClient()


def get_ocr_service(db: Session = Depends(get_db)) -> OcrService:
    return OcrService(
        ocr_repo=OcrRepository(db),
        record_repo=RecordRepository(db),
        ocr_client=_build_ocr_client(),
        file_storage=StubFileStorage(),
        parser=OcrParser(),
        max_retries=settings.ocr_max_retries,
    )


def get_record_service(db: Session = Depends(get_db)) -> RecordService:
    return RecordService(RecordRepository(db), StubFileStorage())
