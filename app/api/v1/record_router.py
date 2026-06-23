import hashlib
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.exceptions import UnsupportedMediaTypeException
from app.core.response import success_response
from app.database.session import get_db
from app.domains.ocr.dependencies import (
    get_file_storage,
    get_ocr_job_runner,
    get_ocr_service,
    get_record_service,
)
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
from app.infrastructure.ocr.format import detect_image_format
from app.infrastructure.storage.file_storage import FileStorage

router = APIRouter()


async def _safe_delete(file_storage: FileStorage, file_url: str) -> None:
    """업로드된 파일을 best-effort로 정리한다(보상 삭제)."""
    try:
        await file_storage.delete(file_url)
    except Exception:  # noqa: BLE001
        pass


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
    db: Session = Depends(get_db),
    ocr_service: OcrService = Depends(get_ocr_service),
    file_storage: FileStorage = Depends(get_file_storage),
    runner: Callable[[int], Awaitable[None]] = Depends(get_ocr_job_runner),
):
    content = await file.read()
    image_format = detect_image_format(content)
    if image_format is None:
        raise UnsupportedMediaTypeException()
    file_hash = hashlib.sha256(content).hexdigest()
    record_repo = RecordRepository(db)
    existing = record_repo.find_by_user_and_hash(user_id, file_hash)
    if existing is not None:
        response.status_code = 200
        return success_response(
            message="이미 업로드된 검진 결과지입니다.",
            data=UploadResponse(record_id=existing.id, ocr_job_id=0).model_dump(),
        )
    key = f"checkups/{user_id}/{file_hash}.{image_format}"
    file_url = await file_storage.upload(key, content)
    try:
        record = record_repo.create_record(user_id, "UPLOAD", file_url, file_hash)
        db.flush()
        job = await ocr_service.create_job(record.id, user_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = record_repo.find_by_user_and_hash(user_id, file_hash)
        if existing is None:
            # dedup 제약이 아닌 다른 무결성 위반이거나 경쟁 트랜잭션이
            # 아직 커밋 전인 경우. 고아 파일을 정리하고 원인을 전파한다.
            await _safe_delete(file_storage, file_url)
            raise
        # 중복 업로드: file_hash가 같아 경로가 동일(멱등)하므로 파일은 보존한다.
        response.status_code = 200
        return success_response(
            message="이미 업로드된 검진 결과지입니다.",
            data=UploadResponse(record_id=existing.id, ocr_job_id=0).model_dump(),
        )
    except Exception:
        # 커밋 실패 등으로 record가 남지 않는 경우 업로드된 파일을 정리한다.
        db.rollback()
        await _safe_delete(file_storage, file_url)
        raise
    background_tasks.add_task(runner, job.id)
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
    file_urls = service.delete_checkup(user_id, record_id)
    db.commit()
    # 커밋이 확정된 뒤에만 비가역 스토리지 삭제를 수행한다(best-effort).
    await service.purge_files(file_urls)
    return success_response(message="검진 기록을 삭제했습니다.")
