import hashlib

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.response import success_response
from app.database.session import get_db
from app.domains.ocr.dependencies import get_ocr_service, get_record_service
from app.domains.ocr.service import OcrService
from app.domains.record.repository import RecordRepository
from app.domains.record.schemas import (
    MetricBulkUpdateRequest,
    MetricResponse,
    MetricUpdateRequest,
    UploadResponse,
    VerifyRequest,
)
from app.domains.record.service import RecordService

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
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    record_repo = RecordRepository(db)
    existing = record_repo.find_by_user_and_hash(user_id, file_hash)
    if existing is not None:
        response.status_code = 200
        return success_response(
            message="이미 업로드된 검진 결과지입니다.",
            data=UploadResponse(record_id=existing.id, ocr_job_id=0).model_dump(),
        )
    file_url = await ocr_service._file_storage.upload(
        f"checkups/{user_id}/{file_hash}.png", content
    )
    record = record_repo.create_record(user_id, "UPLOAD", file_url, file_hash)
    db.flush()
    job = await ocr_service.create_job(record.id, user_id)
    db.commit()
    return success_response(
        message="업로드 완료. OCR 처리를 시작합니다.",
        data=UploadResponse(record_id=record.id, ocr_job_id=job.id).model_dump(),
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
    await service.delete_checkup(user_id, record_id)
    db.commit()
    return success_response(message="검진 기록을 삭제했습니다.")
