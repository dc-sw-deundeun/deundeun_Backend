from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.exceptions import (
    BadRequestException,
    InvalidImageCountException,
    PayloadTooLargeException,
    UnsupportedMediaTypeException,
)
from app.core.response import success_response
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
from app.infrastructure.ocr.encoding import decode_base64_image, normalize_base64_image
from app.infrastructure.ocr.format import detect_image_format

router = APIRouter()


def _metric_list(service: RecordService, user_id: int, record_id: int) -> list[dict]:
    metrics = service.get_metrics(user_id, record_id)
    return [m.model_dump() for m in metrics]


@router.post(
    "/checkups/ocr-preview",
    status_code=200,
    summary="[프론트 사용] 검진 이미지 OCR preview",
    description=(
        "PNG/JPEG 이미지를 base64 문자열 배열로 업로드합니다. data URI와 줄바꿈 포함 base64도 허용합니다. "
        "응답의 metrics를 화면에서 확인·수정한 뒤 `POST /records/checkups`로 저장하세요."
    ),
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "OCR 처리가 완료되었습니다.",
                            "data": {
                                "page_count": 1,
                                "failed_pages": [],
                                "ocr_status": "COMPLETED",
                                "content_hash": "a3f1e2d4b5c6a7e8f9012345678901234567890123456789012345678901234",
                                "metrics": [
                                    {
                                        "metric_code": "fasting_glucose",
                                        "metric_name": "공복혈당",
                                        "value": "95",
                                        "unit": "mg/dL",
                                        "confidence": 0.97,
                                        "raw_text": "공복혈당 95",
                                        "page_index": 0,
                                        "low_confidence": False,
                                        "out_of_range": False,
                                    },
                                    {
                                        "metric_code": "bmi",
                                        "metric_name": "체질량지수",
                                        "value": "22.5",
                                        "unit": "kg/m²",
                                        "confidence": 0.95,
                                        "raw_text": "BMI 22.5",
                                        "page_index": 0,
                                        "low_confidence": False,
                                        "out_of_range": False,
                                    },
                                ],
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
async def preview_checkup_ocr(
    body: MultiImageUploadRequest,
    current_user: CurrentUser = Depends(get_current_user),
    ocr_service: OcrService = Depends(get_ocr_service),
):
    if not (1 <= len(body.images) <= settings.max_images_per_upload):
        raise InvalidImageCountException()

    images: list[bytes] = []
    total_bytes = 0
    for index, encoded in enumerate(body.images, start=1):
        try:
            raw = decode_base64_image(encoded)
        except ValueError as exc:
            had_data_uri = encoded.strip().lower().startswith("data:image/")
            normalized = normalize_base64_image(encoded)
            message = "유효하지 않은 base64 인코딩입니다."
            if had_data_uri and not normalized:
                message = "data URI 형식이지만 base64 payload가 비어 있습니다."
            elif had_data_uri:
                message = (
                    "data URI 형식의 이미지를 디코드하지 못했습니다. "
                    "base64 payload를 확인해 주세요."
                )
            raise BadRequestException(
                message=message,
                error_code="INVALID_IMAGE_FORMAT",
            ) from exc
        if detect_image_format(raw) is None:
            raise UnsupportedMediaTypeException(
                message=f"{index}번째 이미지는 지원하지 않는 형식입니다. PNG 또는 JPEG만 가능합니다."
            )
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


@router.post(
    "/checkups",
    status_code=200,
    summary="[프론트 사용] OCR preview 결과 저장",
    description=(
        "OCR preview 응답의 `ocr_status`, `failed_pages`, `content_hash`, `metrics`를 전달해 "
        "검진 기록을 저장합니다. 같은 `content_hash`는 중복 업로드로 처리됩니다."
    ),
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "검진 기록을 저장했습니다.",
                            "data": {
                                "record_id": 1,
                                "verification_status": "UNVERIFIED",
                                "metrics": [
                                    {
                                        "metric_id": 1,
                                        "metric_code": "fasting_glucose",
                                        "metric_name": "공복혈당",
                                        "value": "95",
                                        "unit": "mg/dL",
                                        "status": "normal",
                                        "reference_min": 70.0,
                                        "reference_max": 100.0,
                                        "confidence": 0.97,
                                        "low_confidence": False,
                                        "source": "OCR",
                                        "is_edited": False,
                                    }
                                ],
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
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


@router.post(
    "/checkups/manual",
    status_code=201,
    summary="[프론트 사용] 수동 검진 기록 생성",
    description="이미지 없이 사용자가 직접 입력한 검진 수치로 기록을 생성합니다.",
)
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


@router.get(
    "/checkups",
    summary="[프론트 사용] 검진 기록 목록 조회",
    description="인증된 사용자의 검진 기록 목록을 페이지 단위로 조회합니다.",
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "요청이 성공했습니다.",
                            "data": {
                                "items": [
                                    {
                                        "record_id": 1,
                                        "source_type": "OCR",
                                        "verification_status": "VERIFIED",
                                        "analysis_status": "COMPLETED",
                                        "ocr_status": "COMPLETED",
                                        "measured_at": "2026-06-01T09:00:00Z",
                                        "created_at": "2026-06-01T09:05:00Z",
                                        "metric_count": 12,
                                    }
                                ],
                                "page": 1,
                                "size": 20,
                                "total": 1,
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
def list_checkups(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    result = service.list_checkups(current_user.id, page=page, size=size)
    return success_response(data=result.model_dump())


@router.get(
    "/checkups/{record_id}",
    summary="[프론트 사용] 검진 기록 상세 조회",
    description="검진 기록의 상태, 측정일, 지표 목록을 조회합니다.",
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "요청이 성공했습니다.",
                            "data": {
                                "record_id": 1,
                                "source_type": "OCR",
                                "verification_status": "VERIFIED",
                                "analysis_status": "COMPLETED",
                                "ocr_status": "COMPLETED",
                                "measured_at": "2026-06-01T09:00:00Z",
                                "verified_at": "2026-06-01T09:10:00Z",
                                "created_at": "2026-06-01T09:05:00Z",
                                "overall_status": "caution",
                                "metrics": [
                                    {
                                        "metric_id": 1,
                                        "metric_code": "fasting_glucose",
                                        "metric_name": "공복혈당",
                                        "value": "105",
                                        "unit": "mg/dL",
                                        "status": "caution",
                                        "reference_min": 70.0,
                                        "reference_max": 100.0,
                                        "confidence": 0.97,
                                        "low_confidence": False,
                                        "source": "OCR",
                                        "is_edited": False,
                                    }
                                ],
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
def get_checkup(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    detail = service.get_checkup(current_user.id, record_id)
    return success_response(data=detail.model_dump())


@router.get(
    "/checkups/{record_id}/trends",
    summary="[프론트 사용] 검진 지표 추세 조회",
    description="선택한 검진 기록의 지표별 추세 데이터를 조회합니다.",
)
def get_checkup_trends(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    trends = service.get_trends(current_user.id, record_id)
    return success_response(data=trends.model_dump())


def _get_db_session():
    from app.database.session import get_db

    yield from get_db()


@router.get(
    "/checkups/{record_id}/analysis",
    summary="[프론트 사용] 검진 기록 최신 HealthMetric 분석 조회",
    description=(
        "검진 기록에 연결된 최신 HealthMetric 분석 1건을 조회합니다. 신규 화면은 "
        "`/analysis/*`가 아니라 이 API 또는 `/health-metrics/analyses/{analysis_id}`를 사용하세요."
    ),
)
def get_checkup_analysis(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(_get_db_session),
):
    from app.domains.health_metric.service import HealthMetricAnalysisService

    analysis = HealthMetricAnalysisService(db).get_latest_for_record(record_id, current_user.id)
    return success_response(data=analysis.model_dump(mode="json"))


@router.get(
    "/checkups/{record_id}/metrics",
    summary="[프론트 사용] 검진 지표 목록 조회",
    description="검진 기록에 포함된 지표 목록만 조회합니다.",
)
def get_checkup_metrics(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    return success_response(data=_metric_list(service, current_user.id, record_id))


@router.patch(
    "/checkups/{record_id}/metrics/{metric_id}",
    summary="[프론트 사용] 검진 지표 단일 수정",
    description="사용자가 확인한 단일 검진 지표의 값과 단위를 수정합니다.",
)
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


@router.put(
    "/checkups/{record_id}/metrics",
    summary="[프론트 사용] 검진 지표 일괄 수정",
    description="검수 화면에서 여러 검진 지표의 값과 단위를 한 번에 수정합니다.",
)
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


@router.post(
    "/checkups/{record_id}/verify",
    summary="[프론트 사용] 검진 검수 완료",
    description=(
        "사용자 확인이 끝난 검진 기록을 VERIFIED로 전환합니다. "
        "온보딩 INITIAL_CHECKUP 단계 사용자는 CHECKUP_VERIFIED 단계로 전이됩니다."
    ),
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "검수를 완료했습니다.",
                            "data": {
                                "record_id": 1,
                                "verification_status": "VERIFIED",
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
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


@router.delete(
    "/checkups/{record_id}",
    summary="[프론트 사용] 검진 기록 삭제",
    description="인증된 사용자의 검진 기록과 관련 지표를 삭제합니다.",
)
async def delete_checkup(
    record_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: RecordService = Depends(get_record_service),
):
    service.delete_checkup(current_user.id, record_id)
    return success_response(message="검진 기록을 삭제했습니다.")
