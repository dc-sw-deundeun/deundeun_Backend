from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from app.domains.ocr.dependencies import get_ocr_service
from app.domains.ocr.schemas import OcrJobResponse
from app.domains.ocr.service import OcrService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "/jobs/{job_id}",
    summary="[프론트 사용] OCR job 상태 조회",
    description=(
        "OCR 작업 상태를 조회합니다. 현재 일반 검진 업로드는 `POST /records/checkups/ocr-preview` "
        "응답을 우선 사용하고, 비동기 상태 확인이 필요한 화면에서만 호출하세요."
    ),
)
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
