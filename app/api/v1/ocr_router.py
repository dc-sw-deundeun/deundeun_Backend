from collections.abc import Awaitable, Callable

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from app.domains.ocr.dependencies import get_ocr_job_runner, get_ocr_service
from app.domains.ocr.schemas import OcrJobResponse
from app.domains.ocr.service import OcrService

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
    service: OcrService = Depends(get_ocr_service),
    runner: Callable[[int], Awaitable[None]] = Depends(get_ocr_job_runner),
):
    job = await service.reprocess(user_id, record_id)
    background_tasks.add_task(runner, job.id)
    return success_response(
        message="OCR 재처리를 요청했습니다.",
        data={"record_id": record_id, "ocr_job_id": job.id},
    )
