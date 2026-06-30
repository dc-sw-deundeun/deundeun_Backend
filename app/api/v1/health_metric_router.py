from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.client_ip import resolve_client_ip
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import rate_limiter
from app.core.response import success_response
from app.database.session import get_db
from app.domains.health_metric.explanation_service import HealthMetricExplanationService
from app.domains.health_metric.schemas import (
    HealthMetricEvaluationRequest,
    HealthMetricEvaluationResponse,
)
from app.domains.health_metric.service import (
    HealthMetricAnalysisService,
    HealthMetricService,
    build_detail_views,
    build_summary_view,
)
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.post(
    "/evaluate",
    summary="[프론트 사용] 건강검진 항목 평가",
    description=(
        "검진 항목 label/value/unit을 표준 지표와 매칭하고 정상·주의·위험 상태, 설명, "
        "UI용 summary/detail view를 반환합니다. 로그인 없이 호출 가능하며 IP 기준 rate limit이 적용됩니다."
    ),
)
async def evaluate_health_metrics(
    request: HealthMetricEvaluationRequest,
    http_request: Request,
):
    _check_evaluate_rate_limit(http_request)
    service = HealthMetricService()
    results = service.evaluate_metrics(request)
    explanation = await HealthMetricExplanationService().build_explanation(
        request=request,
        results=results,
    )
    summary = build_summary_view(results=results, explanation=explanation)
    details = build_detail_views(results=results, explanation=explanation)
    response = HealthMetricEvaluationResponse(
        results=results,
        explanation=explanation,
        ui={
            "summary": summary.model_dump(mode="json"),
            "details": [detail.model_dump(mode="json") for detail in details],
        },
    )
    return success_response(
        message="건강검진 항목 판정이 완료되었습니다.",
        data=response.model_dump(mode="json"),
    )


@router.post(
    "/analyses",
    summary="[프론트 사용] 건강검진 분석 저장",
    description=(
        "인증된 사용자의 건강검진 항목 평가 결과를 저장하고 `/evaluate`와 동일한 results, explanation, "
        "ui.summary, ui.details에 analysis_id와 record_id를 함께 반환합니다. record_id를 전달하면 "
        "사용자 소유 VERIFIED 검진 기록만 허용하고, 성공 시 해당 기록의 analysis_status를 COMPLETED로 갱신합니다."
    ),
)
async def create_health_metric_analysis(
    request: HealthMetricEvaluationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_analysis_rate_limit(current_user.id)
    response = await HealthMetricAnalysisService(db).create(
        request=request,
        user_id=current_user.id,
        measured_at=_parse_measured_at(request.measured_at),
    )
    return success_response(
        message="건강검진 분석이 생성되었습니다.",
        data=response.model_dump(mode="json"),
    )


@router.get(
    "/analyses/{analysis_id}",
    summary="[프론트 사용] 건강검진 분석 조회",
    description=(
        "저장된 건강검진 분석을 조회합니다. 응답은 POST /health-metrics/analyses와 동일하게 "
        "results, explanation, ui.summary, ui.details를 포함합니다."
    ),
)
async def get_health_metric_analysis(
    analysis_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    response = HealthMetricAnalysisService(db).get(analysis_id, current_user.id)
    return success_response(data=response.model_dump(mode="json"))


def _client_ip(request: Request) -> str:
    return resolve_client_ip(
        direct_client_host=request.client.host if request.client else None,
        forwarded_for=request.headers.get("X-Forwarded-For"),
        trusted_proxy=settings.trusted_proxy,
        trusted_proxy_cidrs=cast(list[str], settings.trusted_proxy_cidrs),
    )


def _check_evaluate_rate_limit(request: Request) -> None:
    rate_limiter.check(
        key=f"health-metric:evaluate:ip:{_client_ip(request)}",
        limit=settings.health_metric_evaluate_rate_limit_per_minute,
    )


def _check_analysis_rate_limit(user_id: int) -> None:
    rate_limiter.check(
        key=f"health-metric:analysis:user:{user_id}",
        limit=settings.health_metric_analysis_rate_limit_per_minute,
    )


def _parse_measured_at(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="measured_at must be ISO date format, e.g. 2026-06-25",
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
