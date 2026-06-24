import hashlib
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.exceptions import (
    PayloadTooLargeException,
    UnsupportedMediaTypeException,
)
from app.core.response import not_implemented_response, success_response
from app.database.session import get_db
from app.domains.ocr.dependencies import (
    get_ocr_job_runner,
    get_ocr_service,
    get_record_service,
)
from app.domains.ocr.service import OcrService
from app.domains.record.schemas import (
    MetricBulkUpdateRequest,
    MetricResponse,
    MetricUpdateRequest,
    UploadResponse,
    VerifyRequest,
)
from app.domains.record.service import RecordService
from app.domains.user.schemas import CurrentUser
from app.infrastructure.ocr.format import detect_image_format

router = APIRouter()


def _metric_list(service: RecordService, user_id: int, record_id: int) -> list[dict]:
    metrics = service.get_metrics(user_id, record_id)
    return [
        MetricResponse.from_model(m, settings.ocr_min_confidence).model_dump()
        for m in metrics
    ]


@router.post("/checkups/upload", status_code=202)
async def upload_checkup(
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    ocr_service: OcrService = Depends(get_ocr_service),
    runner: Callable[[int], Awaitable[None]] = Depends(get_ocr_job_runner),
):
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise PayloadTooLargeException()
    image_format = detect_image_format(content)
    if image_format is None:
        raise UnsupportedMediaTypeException()
    file_hash = hashlib.sha256(content).hexdigest()

    result = await ocr_service.upload_checkup(
        current_user.id, content, image_format, file_hash
    )
    if result.is_duplicate:
        response.status_code = 200
        return success_response(
            message="이미 업로드된 검진 결과지입니다.",
            data=UploadResponse(record_id=result.record_id, ocr_job_id=None).model_dump(),
        )
    background_tasks.add_task(runner, result.job_id)
    return success_response(
        message="업로드 완료. OCR 처리를 시작합니다.",
        data=UploadResponse(
            record_id=result.record_id, ocr_job_id=result.job_id
        ).model_dump(),
    )


@router.get("/checkups")
async def list_checkups(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/checkups/{record_id}")
async def get_checkup(
    record_id: int, current_user: CurrentUser = Depends(get_current_user)
):
    return not_implemented_response()


@router.get("/checkups/{record_id}/metrics")
def get_checkup_metrics(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    return success_response(data=_metric_list(service, current_user.id, record_id))


@router.patch("/checkups/{record_id}/metrics/{metric_id}")
def update_metric(
    record_id: int,
    metric_id: int,
    body: MetricUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: RecordService = Depends(get_record_service),
):
    metric = service.update_metric(
        current_user.id, record_id, metric_id, body.value, body.unit
    )
    db.commit()
    return success_response(
        message="수치를 수정했습니다.",
        data=MetricResponse.from_model(metric, settings.ocr_min_confidence).model_dump(),
    )


@router.put("/checkups/{record_id}/metrics")
def bulk_update_metrics(
    record_id: int,
    body: MetricBulkUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: RecordService = Depends(get_record_service),
):
    service.bulk_update_metrics(current_user.id, record_id, body.metrics)
    db.commit()
    return success_response(
        message="수치를 일괄 수정했습니다.",
        data=_metric_list(service, current_user.id, record_id),
    )


@router.post("/checkups/{record_id}/verify")
def verify_checkup(
    record_id: int,
    body: VerifyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: RecordService = Depends(get_record_service),
):
    record = service.verify(current_user.id, record_id, body.metrics)
    db.commit()
    return success_response(
        message="검수를 완료했습니다.",
        data={"record_id": record.id, "verification_status": record.verification_status},
    )


@router.delete("/checkups/{record_id}")
async def delete_checkup(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: RecordService = Depends(get_record_service),
):
    file_urls = service.delete_checkup(current_user.id, record_id)
    db.commit()
    # 커밋이 확정된 뒤에만 비가역 스토리지 삭제를 수행한다(best-effort).
    await service.purge_files(file_urls)
    return success_response(message="검진 기록을 삭제했습니다.")


@router.post("/meals")
async def create_meal_record(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/meals")
async def list_meal_records(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()
