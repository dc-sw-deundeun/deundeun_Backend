from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from app.domains.ocr.dependencies import get_ocr_service
from app.domains.ocr.schemas import OcrJobResponse
from app.domains.ocr.service import OcrService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get("/jobs/{job_id}")
def get_job_status(
    job_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: OcrService = Depends(get_ocr_service),
):
    job = service.get_job(job_id)
    if job is None or job.user_id != current_user.id:
        raise NotFoundException(message="OCR 작업을 찾을 수 없습니다.")
    data = OcrJobResponse(
        job_id=job.id,
        record_id=job.record_id,
        status=job.status,
        parsed_field_count=job.parsed_field_count,
        error_message=job.error_message,
    )
    return success_response(data=data.model_dump())
