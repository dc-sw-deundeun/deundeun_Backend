from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import rate_limiter
from app.core.response import success_response
from app.database.session import get_db
from app.domains.health_metric.schemas import HealthMetricEvaluationRequest
from app.domains.health_metric.service import HealthMetricAnalysisService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.post(
    "/analyses",
    summary="[프론트 사용] 건강검진 분석 저장",
    description=(
        "인증된 사용자의 건강검진 항목 평가 결과를 저장하고 results, explanation, ui.summary, "
        "ui.details에 analysis_id와 record_id를 함께 반환합니다. record_id를 전달하면 "
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
