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
from app.core.response import success_response
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
    user_id: int = Depends(get_current_user),
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

    result = await ocr_service.upload_checkup(user_id, content, image_format, file_hash)
    if result.is_duplicate:
        response.status_code = 200
        return success_response(
            message="이미 업로드된 검진 결과지입니다.",
            data=UploadResponse(record_id=result.record_id, ocr_job_id=0).model_dump(),
        )
    background_tasks.add_task(runner, result.job_id)
    return success_response(
        message="업로드 완료. OCR 처리를 시작합니다.",
        data=UploadResponse(
            record_id=result.record_id, ocr_job_id=result.job_id
        ).model_dump(),
    )


@router.get("/checkups/{record_id}/metrics")
def get_checkup_metrics(
    record_id: int,
    user_id: int = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    return success_response(data=_metric_list(service, user_id, record_id))


@router.patch("/checkups/{record_id}/metrics/{metric_id}")
def update_metric(
    record_id: int,
    metric_id: int,
    body: MetricUpdateRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: RecordService = Depends(get_record_service),
):
    metric = service.update_metric(user_id, record_id, metric_id, body.value, body.unit)
    db.commit()
    return success_response(
        message="수치를 수정했습니다.",
        data=MetricResponse.from_model(metric, settings.ocr_min_confidence).model_dump(),
    )


@router.put("/checkups/{record_id}/metrics")
def bulk_update_metrics(
    record_id: int,
    body: MetricBulkUpdateRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: RecordService = Depends(get_record_service),
):
    service.bulk_update_metrics(user_id, record_id, body.metrics)
    db.commit()
    return success_response(
        message="수치를 일괄 수정했습니다.",
        data=_metric_list(service, user_id, record_id),
    )


@router.post("/checkups/{record_id}/verify")
def verify_checkup(
    record_id: int,
    body: VerifyRequest,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: RecordService = Depends(get_record_service),
):
    record = service.verify(user_id, record_id, body.metrics)
    db.commit()
    return success_response(
        message="검수를 완료했습니다.",
        data={"record_id": record.id, "verification_status": record.verification_status},
    )


@router.delete("/checkups/{record_id}")
async def delete_checkup(
    record_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: RecordService = Depends(get_record_service),
):
    file_urls = service.delete_checkup(user_id, record_id)
    db.commit()
    # 커밋이 확정된 뒤에만 비가역 스토리지 삭제를 수행한다(best-effort).
    await service.purge_files(file_urls)
    return success_response(message="검진 기록을 삭제했습니다.")
