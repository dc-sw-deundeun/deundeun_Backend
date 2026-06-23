from collections.abc import Awaitable, Callable

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.response import success_response
from app.database.session import get_db
from app.domains.ocr.dependencies import get_file_storage, get_ocr_job_runner, get_ocr_service
from app.domains.ocr.schemas import OcrJobResponse
from app.domains.ocr.service import OcrService
from app.domains.record.repository import RecordRepository
from app.infrastructure.storage.file_storage import FileStorage

router = APIRouter()


@router.get("/jobs/{job_id}")
def get_job_status(
    job_id: int,
    user_id: int = Depends(get_current_user),
    service: OcrService = Depends(get_ocr_service),
):
    job = service.get_job(job_id)
    if job is None or job.user_id != user_id:
        raise NotFoundException(message="OCR 작업을 찾을 수 없습니다.")
    data = OcrJobResponse(
        job_id=job.id, record_id=job.record_id, status=job.status,
        parsed_field_count=job.parsed_field_count, error_message=job.error_message,
    )
    return success_response(data=data.model_dump())


@router.post("/checkups/{record_id}/reprocess")
async def reprocess(
    record_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OcrService = Depends(get_ocr_service),
    file_storage: FileStorage = Depends(get_file_storage),
    runner: Callable[[int], Awaitable[None]] = Depends(get_ocr_job_runner),
):
    record_repo = RecordRepository(db)
    record = record_repo.get_record(record_id)
    if record is None:
        raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
    if record.user_id != user_id:
        raise ForbiddenException(message="해당 기록에 대한 권한이 없습니다.")
    if not record.file_url or not await file_storage.exists(record.file_url):
        raise ConflictException(
            message="원본 이미지가 없어 재처리할 수 없습니다.",
            error_code="IMAGE_UNAVAILABLE",
        )
    record_repo.reset_verification(record)
    record_repo.set_ocr_status(record, "PENDING")
    job = await service.create_job(record_id, user_id)
    db.commit()
    background_tasks.add_task(runner, job.id)
    return success_response(
        message="OCR 재처리를 요청했습니다.",
        data={"record_id": record_id, "ocr_job_id": job.id},
    )
