from collections.abc import Awaitable, Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db, session_scope
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.record.repository import RecordRepository
from app.domains.record.service import RecordService
from app.infrastructure.ocr.clova_client import ClovaOcrClient
from app.infrastructure.ocr.ocr_client import StubOcrClient
from app.infrastructure.ocr.parser import OcrParser
from app.infrastructure.storage.file_storage import FileStorage, LocalFileStorage


def get_file_storage() -> FileStorage:
    return LocalFileStorage(settings.local_storage_dir)


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
        file_storage=get_file_storage(),
        parser=OcrParser(),
        max_retries=settings.ocr_max_retries,
    )


def get_ocr_service(db: Session = Depends(get_db)) -> OcrService:
    return build_ocr_service(db)


def get_record_service(db: Session = Depends(get_db)) -> RecordService:
    return RecordService(RecordRepository(db), get_file_storage())


def get_ocr_job_runner() -> Callable[[int], Awaitable[None]]:
    async def _run(job_id: int) -> None:
        with session_scope() as db:
            service = build_ocr_service(db)
            await service.process_single(job_id)

    return _run
