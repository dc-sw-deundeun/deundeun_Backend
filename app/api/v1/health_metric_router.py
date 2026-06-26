from datetime import UTC, datetime

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
    HealthMetricAnalysisCreateResponse,
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


@router.post("/evaluate")
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


@router.post("/analyses")
async def create_health_metric_analysis(
    request: HealthMetricEvaluationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _check_analysis_rate_limit(current_user.id)
    analysis_id, summary = await HealthMetricAnalysisService(db).create(
        request=request,
        user_id=current_user.id,
        measured_at=_parse_measured_at(request.measured_at),
    )
    response = HealthMetricAnalysisCreateResponse(analysis_id=analysis_id, summary=summary)
    return success_response(
        message="건강검진 분석이 생성되었습니다.",
        data=response.model_dump(mode="json"),
    )


def _client_ip(request: Request) -> str:
    return resolve_client_ip(
        direct_client_host=request.client.host if request.client else None,
        forwarded_for=request.headers.get("X-Forwarded-For"),
        trusted_proxy=settings.trusted_proxy,
        trusted_proxy_cidrs=settings.trusted_proxy_cidrs,
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
