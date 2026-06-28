import base64

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.exceptions import (
    BadRequestException,
    InvalidImageCountException,
    PayloadTooLargeException,
    UnsupportedMediaTypeException,
)
from app.core.response import not_implemented_response, success_response
from app.domains.ocr.dependencies import get_ocr_service, get_record_service
from app.domains.ocr.service import FinalMetric, OcrService
from app.domains.record.content_hash import compute_content_hash
from app.domains.record.schemas import (
    CommitCheckupRequest,
    CommitCheckupResponse,
    ManualCheckupRequest,
    MetricBulkUpdateRequest,
    MetricResponse,
    MetricUpdateRequest,
    MultiImageUploadRequest,
    PreviewMetricResponse,
    UploadResponse,
    VerifyRequest,
)
from app.domains.record.service import RecordService
from app.domains.user.schemas import CurrentUser
from app.infrastructure.ocr.format import detect_image_format

router = APIRouter()


def _metric_list(service: RecordService, user_id: int, record_id: int) -> list[dict]:
    metrics = service.get_metrics(user_id, record_id)
    return [m.model_dump() for m in metrics]


@router.post("/checkups/upload", status_code=200)
async def upload_checkup(
    body: MultiImageUploadRequest,
    current_user: CurrentUser = Depends(get_current_user),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    return await preview_checkup_ocr(body, current_user, ocr_service)


@router.post("/checkups/ocr-preview", status_code=200)
async def preview_checkup_ocr(
    body: MultiImageUploadRequest,
    current_user: CurrentUser = Depends(get_current_user),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    if not (1 <= len(body.images) <= settings.max_images_per_upload):
        raise InvalidImageCountException()

    images: list[bytes] = []
    total_bytes = 0
    for encoded in body.images:
        try:
            raw = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise BadRequestException(
                message="유효하지 않은 base64 인코딩입니다.",
                error_code="INVALID_IMAGE_FORMAT",
            ) from exc
        if detect_image_format(raw) is None:
            raise UnsupportedMediaTypeException()
        total_bytes += len(raw)
        if len(raw) > settings.max_single_upload_size_bytes:
            max_mb = settings.max_single_upload_size_bytes // (1024 * 1024)
            raise PayloadTooLargeException(message=f"단일 이미지가 {max_mb}MB를 초과했습니다.")
        images.append(raw)

    if total_bytes > settings.max_total_upload_size_bytes:
        max_total_mb = settings.max_total_upload_size_bytes // (1024 * 1024)
        raise PayloadTooLargeException(
            message=f"전체 이미지 합계가 {max_total_mb}MB를 초과했습니다."
        )

    content_hash = compute_content_hash(images)
    outcome = await ocr_service.process_upload(current_user.id, images, content_hash=content_hash)

    metrics = [
        PreviewMetricResponse.from_parsed(metric, settings.ocr_min_confidence)
        for metric in outcome.metrics
    ]
    message = (
        "OCR 처리가 완료되었습니다."
        if not outcome.failed_pages
        else f"{len(outcome.failed_pages)}개 페이지 처리에 실패했습니다."
    )
    return success_response(
        message=message,
        data=UploadResponse(
            page_count=outcome.page_count,
            failed_pages=outcome.failed_pages,
            ocr_status=outcome.ocr_status,
            content_hash=outcome.content_hash,
            metrics=metrics,
        ).model_dump(),
    )


@router.post("/checkups", status_code=200)
def commit_checkup(
    body: CommitCheckupRequest,
    current_user: CurrentUser = Depends(get_current_user),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    outcome = ocr_service.commit_upload(
        current_user.id,
        ocr_status=body.ocr_status,
        failed_pages=body.failed_pages,
        content_hash=body.content_hash,
        metrics=[
            FinalMetric(
                metric_code=metric.metric_code,
                metric_name=metric.metric_name,
                value=metric.value,
                unit=metric.unit,
                confidence=metric.confidence,
                raw_text=metric.raw_text,
                page_index=metric.page_index,
                is_edited=metric.is_edited,
            )
            for metric in body.metrics
        ],
    )
    message = (
        "이미 업로드된 검진 결과지입니다." if outcome.is_duplicate else "검진 기록을 저장했습니다."
    )
    return success_response(
        message=message,
        data=CommitCheckupResponse(
            record_id=outcome.record_id,
            verification_status=outcome.verification_status,
            metrics=[
                MetricResponse.from_model(metric, settings.ocr_min_confidence)
                for metric in outcome.metrics
            ],
        ).model_dump(),
    )


@router.post("/checkups/manual", status_code=201)
def create_manual_checkup(
    body: ManualCheckupRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    record = service.create_manual(current_user.id, body)
    metrics = service.get_metrics(current_user.id, record.id)
    return success_response(
        message="검진 기록을 저장했습니다.",
        data={
            "record_id": record.id,
            "verification_status": record.verification_status,
            "metrics": [m.model_dump() for m in metrics],
        },
    )


@router.get("/checkups")
def list_checkups(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    result = service.list_checkups(current_user.id, page=page, size=size)
    return success_response(data=result.model_dump())


@router.get("/checkups/{record_id}")
def get_checkup(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    detail = service.get_checkup(current_user.id, record_id)
    return success_response(data=detail.model_dump())


@router.get("/checkups/{record_id}/trends")
def get_checkup_trends(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    trends = service.get_trends(current_user.id, record_id)
    return success_response(data=trends.model_dump())


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
    service: RecordService = Depends(get_record_service),
):
    metric = service.update_metric(current_user.id, record_id, metric_id, body.value, body.unit)
    return success_response(
        message="수치를 수정했습니다.",
        data=metric.model_dump(),
    )


@router.put("/checkups/{record_id}/metrics")
def bulk_update_metrics(
    record_id: int,
    body: MetricBulkUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    metrics = service.bulk_update_metrics(current_user.id, record_id, body.metrics)
    return success_response(
        message="수치를 일괄 수정했습니다.",
        data=[m.model_dump() for m in metrics],
    )


@router.post("/checkups/{record_id}/verify")
def verify_checkup(
    record_id: int,
    body: VerifyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    record = service.verify(current_user.id, record_id, body.metrics)
    return success_response(
        message="검수를 완료했습니다.",
        data={"record_id": record.id, "verification_status": record.verification_status},
    )


@router.delete("/checkups/{record_id}")
async def delete_checkup(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    service.delete_checkup(current_user.id, record_id)
    return success_response(message="검진 기록을 삭제했습니다.")


@router.post("/meals")
async def create_meal_record(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get("/meals")
async def list_meal_records(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()
