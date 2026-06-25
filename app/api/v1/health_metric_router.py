from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.database.session import get_db
from app.core.response import success_response
from app.domains.health_metric.models import HealthMetricAnalysis
from app.domains.health_metric.repository import HealthMetricAnalysisRepository
from app.domains.health_metric.schemas import (
    HealthMetricAnalysisCreateResponse,
    HealthMetricEvaluationRequest,
    HealthMetricEvaluationResponse,
)
from app.domains.health_metric.explanation_service import HealthMetricExplanationService
from app.domains.health_metric.service import (
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
    service = HealthMetricService()
    results = service.evaluate_metrics(request)
    explanation = await HealthMetricExplanationService().build_explanation(
        request=request,
        results=results,
    )

    analysis = HealthMetricAnalysis(
        user_id=current_user.id,
        sex=request.sex,
        measured_at=_parse_measured_at(request.measured_at),
        request_payload=request.model_dump(mode="json"),
        results_payload=[item.model_dump(mode="json") for item in results],
        explanation_payload=explanation.model_dump(mode="json"),
        summary_payload={},
        details_payload=[],
    )
    db.add(analysis)
    db.flush()

    summary = build_summary_view(
        results=results,
        explanation=explanation,
        analysis_id=analysis.id,
    )
    details = build_detail_views(
        results=results,
        explanation=explanation,
        analysis_id=analysis.id,
    )
    analysis.summary_payload = summary.model_dump(mode="json")
    analysis.details_payload = [detail.model_dump(mode="json") for detail in details]
    db.commit()
    db.refresh(analysis)

    response = HealthMetricAnalysisCreateResponse(
        analysis_id=analysis.id,
        summary=summary,
    )
    return success_response(
        message="건강검진 분석이 생성되었습니다.",
        data=response.model_dump(mode="json"),
    )


@router.get("/analyses/{analysis_id}/summary")
async def get_health_metric_analysis_summary(
    analysis_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analysis = _get_analysis_or_404(analysis_id, current_user.id, db)
    return success_response(data=analysis.summary_payload)


@router.get("/analyses/{analysis_id}/details/{metric_code}")
async def get_health_metric_analysis_detail(
    analysis_id: int,
    metric_code: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analysis = _get_analysis_or_404(analysis_id, current_user.id, db)
    repo = HealthMetricAnalysisRepository(db)
    normalized_code = metric_code.strip().upper()
    for detail in analysis.details_payload:
        metric = detail.get("metric", {})
        code = metric.get("code")
        label = metric.get("label")
        if (code and code.upper() == normalized_code) or (
            label and label.upper() == normalized_code
        ):
            detail = dict(detail)
            detail["trend"] = _build_metric_trend(
                analyses=repo.list_until(
                    analysis.measured_at or analysis.created_at,
                    user_id=current_user.id,
                ),
                metric_code=code or normalized_code,
            )
            return success_response(data=detail)
    raise HTTPException(status_code=404, detail="Health metric detail not found")


def _get_analysis_or_404(
    analysis_id: int, user_id: int, db: Session
) -> HealthMetricAnalysis:
    analysis = HealthMetricAnalysisRepository(db).get(analysis_id)
    if analysis is None or analysis.user_id != user_id:
        raise HTTPException(status_code=404, detail="Health metric analysis not found")
    return analysis


def _check_evaluate_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    rate_limiter.check(
        key=f"health-metric:evaluate:ip:{client_host}",
        limit=settings.health_metric_evaluate_rate_limit_per_minute,
    )


def _check_analysis_rate_limit(user_id: int) -> None:
    rate_limiter.check(
        key=f"health-metric:analysis:user:{user_id}",
        limit=settings.health_metric_analysis_rate_limit_per_minute,
    )


def _build_metric_trend(
    analyses: list[HealthMetricAnalysis],
    metric_code: str,
) -> dict:
    points = []
    normalized_code = metric_code.upper()
    dated_analyses = [analysis for analysis in analyses if analysis.measured_at is not None]
    current_analysis = max(dated_analyses, key=lambda item: item.id) if dated_analyses else None
    current_date = current_analysis.measured_at if current_analysis is not None else datetime.now(UTC)
    for analysis in sorted(dated_analyses, key=_analysis_date):
        value = _find_metric_value(analysis.results_payload, normalized_code)
        if value is None:
            continue
        points.append(
            {
                "label": _trend_label(analysis, current_date.year),
                "value": value,
            }
        )
    return {"title": "최근 추이", "points": points}


def _find_metric_value(results_payload: list, metric_code: str) -> float | None:
    for item in results_payload:
        code = item.get("canonical_test_code")
        if code and code.upper() == metric_code:
            value = item.get("value")
            return float(value) if value is not None else None
    return None


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


def _trend_label(analysis: HealthMetricAnalysis, current_year: int) -> str:
    measured_at = _analysis_date(analysis)
    if measured_at.year == current_year:
        return measured_at.strftime("%m.%d")
    return measured_at.strftime("%Y.%m.%d")


def _analysis_date(analysis: HealthMetricAnalysis) -> datetime:
    return analysis.measured_at or analysis.created_at
