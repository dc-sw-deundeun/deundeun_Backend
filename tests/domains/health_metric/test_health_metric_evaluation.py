import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.domains.auth.models  # noqa: F401
import app.domains.health_metric.models  # noqa: F401
import app.domains.user.models  # noqa: F401
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import rate_limiter
from app.database.base import Base
from app.database.session import get_db
from app.domains.health_metric.explanation_service import HealthMetricExplanationService
from app.domains.health_metric.models import HealthMetricAnalysis
from app.domains.health_metric.schemas import HealthMetricEvaluationRequest, HealthMetricInput
from app.domains.health_metric.service import (
    HealthMetricService,
    build_detail_views,
    build_summary_view,
)
from app.domains.user.models import OnboardingStep, User
from app.domains.user.schemas import CurrentUser
from app.main import app as fastapi_app


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    rate_limiter.clear()
    yield
    rate_limiter.clear()


def _result_by_code(results, code: str):
    return next(item for item in results if item.canonical_test_code == code)


def _metric(
    label: str,
    value: float,
    *,
    unit: str | None = None,
    item9_positive: bool | None = None,
) -> HealthMetricInput:
    return HealthMetricInput(
        label=label,
        value=value,
        unit=unit,
        item9_positive=item9_positive,
    )


def _create_user(db_session, *, user_id: int = 1) -> None:
    db_session.add(
        User(
            id=user_id,
            email=f"health-metric-{user_id}@example.com",
            password_hash="hash",
            nickname="health-metric-user",
            onboarding_step=OnboardingStep.INITIAL_CHECKUP.value,
            timezone="Asia/Seoul",
        )
    )
    db_session.commit()


def test_evaluate_metrics_classifies_normal_caution_and_risk() -> None:
    request = HealthMetricEvaluationRequest(
        sex="male",
        metrics=[
            _metric("BMI", 22.0),
            _metric("LDL", 130.0),
            _metric("중성지방", 510.0),
            _metric("허리둘레", 92.0),
        ],
    )

    results = HealthMetricService().evaluate_metrics(request)

    assert _result_by_code(results, "BMI").status == "normal"
    assert _result_by_code(results, "LDL").status == "caution"
    tg = _result_by_code(results, "TG")
    assert tg.status == "risk"
    assert tg.note == "매우 높음"
    assert _result_by_code(results, "WAIST").status == "risk"


@pytest.mark.parametrize(
    ("value", "expected_status"),
    [
        (24.9, "normal"),
        (24.91, "caution"),
        (25.0, "caution"),
        (29.99, "caution"),
        (30.0, "risk"),
    ],
)
def test_bmi_boundary_has_no_gap(value: float, expected_status: str) -> None:
    request = HealthMetricEvaluationRequest(
        metrics=[_metric("BMI", value)],
    )

    result = HealthMetricService().evaluate_metrics(request)[0]

    assert result.status == expected_status


def test_sex_specific_metric_aliases_override_request_sex() -> None:
    request = HealthMetricEvaluationRequest(
        sex="female",
        metrics=[
            _metric("HGB_M", 12.9),
            _metric("GGT_F", 36),
        ],
    )

    results = HealthMetricService().evaluate_metrics(request)

    hgb = _result_by_code(results, "HGB")
    ggt = _result_by_code(results, "GGT")
    assert hgb.status == "risk"
    assert hgb.note == "빈혈 의심"
    assert ggt.status == "risk"
    assert ggt.matched_rule == "female GGT > 35"


def test_unknown_metric_returns_unknown_item() -> None:
    request = HealthMetricEvaluationRequest(
        metrics=[_metric("지원안함", 1.0)],
    )

    result = HealthMetricService().evaluate_metrics(request)[0]

    assert result.status == "unknown"
    assert result.status_label == "판정불가"
    assert result.canonical_test_code is None


def test_evaluate_endpoint_is_removed() -> None:
    with TestClient(fastapi_app) as client:
        response = client.post(
            "/api/v1/health-metrics/evaluate",
            json={"metrics": [{"label": "LDL", "value": 130}]},
        )

    assert response.status_code == 404


def test_builds_summary_and_detail_view_models() -> None:
    request = HealthMetricEvaluationRequest(
        sex="male",
        metrics=[
            _metric("LDL", 190),
            _metric("공복혈당", 110),
        ],
    )
    results = HealthMetricService().evaluate_metrics(request)
    explanation = HealthMetricExplanationService(api_key=None)._fallback(results)

    summary = build_summary_view(results, explanation, analysis_id=10)
    details = build_detail_views(results, explanation, analysis_id=10)

    assert summary.analysis_id == 10
    assert summary.overall.title == "관리가 필요해요"
    assert summary.overall.counts["risk"] == 1
    assert summary.cards[0].range_bar is not None
    assert details[0].metric.code == "LDL"
    assert details[0].meaning.body
    assert details[0].recommendations.items


def test_create_analysis_requires_authentication(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    with TestClient(fastapi_app) as client:
        response = client.post(
            "/api/v1/health-metrics/analyses",
            json={
                "sex": "male",
                "metrics": [
                    {
                        "metric_code": "ldl",
                        "metric_name": "LDL콜레스테롤",
                        "value": "150",
                        "unit": "mg/dL",
                        "raw_text": "150",
                    }
                ],
            },
        )

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_create_analysis_rate_limit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "health_metric_analysis_rate_limit_per_minute", 1)
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    previous_override = fastapi_app.dependency_overrides.get(get_db)
    previous_user_override = fastapi_app.dependency_overrides.get(get_current_user)
    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=1)
    try:
        with TestClient(fastapi_app) as client:
            first = client.post(
                "/api/v1/health-metrics/analyses",
                json={
                    "sex": "male",
                    "metrics": [
                        {
                            "metric_code": "ldl",
                            "metric_name": "LDL콜레스테롤",
                            "value": "150",
                            "unit": "mg/dL",
                            "raw_text": "150",
                        }
                    ],
                },
            )
            second = client.post(
                "/api/v1/health-metrics/analyses",
                json={
                    "sex": "male",
                    "metrics": [
                        {
                            "metric_code": "ldl",
                            "metric_name": "LDL콜레스테롤",
                            "value": "150",
                            "unit": "mg/dL",
                            "raw_text": "150",
                        }
                    ],
                },
            )

        assert first.status_code == 200
        assert first.json()["data"] is None
        assert second.status_code == 429
        assert second.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
    finally:
        if previous_override is None:
            fastapi_app.dependency_overrides.pop(get_db, None)
        else:
            fastapi_app.dependency_overrides[get_db] = previous_override
        if previous_user_override is None:
            fastapi_app.dependency_overrides.pop(get_current_user, None)
        else:
            fastapi_app.dependency_overrides[get_current_user] = previous_user_override


def test_create_analysis_from_metric_array_returns_void_and_get_returns_result(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    user_id = 1
    _create_user(db_session, user_id=user_id)

    previous_user_override = fastapi_app.dependency_overrides.get(get_current_user)
    fastapi_app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)
    try:
        create_response = client.post(
            "/api/v1/health-metrics/analyses",
            json={
                "sex": "male",
                "measured_at": "2026-06-20",
                "metrics": [
                    {
                        "metric_code": "height",
                        "metric_name": "신장",
                        "value": "172.0",
                        "unit": "cm",
                        "raw_text": "172.0",
                    },
                    {
                        "metric_code": "fasting_glucose",
                        "metric_name": "공복혈당",
                        "value": "126",
                        "unit": "mg/dL",
                        "raw_text": "126",
                    },
                    {
                        "metric_code": "urine_protein",
                        "metric_name": "요단백",
                        "value": "음성",
                        "unit": "",
                        "raw_text": "음성",
                    },
                    {
                        "metric_code": "ldl",
                        "metric_name": "LDL콜레스테롤",
                        "value": "160",
                        "unit": "mg/dL",
                        "raw_text": "160",
                    },
                ],
            },
        )

        assert create_response.status_code == 200
        assert create_response.json()["data"] is None
        analysis = db_session.query(HealthMetricAnalysis).one()

        get_response = client.get(f"/api/v1/health-metrics/analyses/{analysis.id}")
        assert get_response.status_code == 200
        data = get_response.json()["data"]
        assert data["analysis_id"] == analysis.id
        assert data["record_id"] is None
        assert [item["canonical_test_code"] for item in data["results"]] == ["FPG", "LDL"]
        assert data["ui"]["summary"]["analysis_id"] == analysis.id
        assert data["ui"]["details"][0]["trend"]["points"] == [
            {"label": "2026-06-20", "value": 126.0}
        ]
    finally:
        if previous_user_override is None:
            fastapi_app.dependency_overrides.pop(get_current_user, None)
        else:
            fastapi_app.dependency_overrides[get_current_user] = previous_user_override


def test_create_analysis_trends_use_previous_saved_analyses(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    user_id = 1
    _create_user(db_session, user_id=user_id)

    previous_user_override = fastapi_app.dependency_overrides.get(get_current_user)
    fastapi_app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)
    try:
        old_response = client.post(
            "/api/v1/health-metrics/analyses",
            json={
                "sex": "male",
                "measured_at": "2026-03-22",
                "metrics": [
                    {
                        "metric_code": "fasting_glucose",
                        "metric_name": "공복혈당",
                        "value": "104",
                        "unit": "mg/dL",
                        "raw_text": "104",
                    }
                ],
            },
        )
        new_response = client.post(
            "/api/v1/health-metrics/analyses",
            json={
                "sex": "male",
                "measured_at": "2026-06-20",
                "metrics": [
                    {
                        "metric_code": "fasting_glucose",
                        "metric_name": "공복혈당",
                        "value": "126",
                        "unit": "mg/dL",
                        "raw_text": "126",
                    }
                ],
            },
        )

        assert old_response.status_code == 200
        assert new_response.status_code == 200
        latest_analysis = (
            db_session.query(HealthMetricAnalysis).order_by(HealthMetricAnalysis.id.desc()).first()
        )
        get_response = client.get(f"/api/v1/health-metrics/analyses/{latest_analysis.id}")

        assert get_response.status_code == 200
        assert get_response.json()["data"]["ui"]["details"][0]["trend"]["points"] == [
            {"label": "2026-03-22", "value": 104.0},
            {"label": "2026-06-20", "value": 126.0},
        ]
    finally:
        if previous_user_override is None:
            fastapi_app.dependency_overrides.pop(get_current_user, None)
        else:
            fastapi_app.dependency_overrides[get_current_user] = previous_user_override


def test_create_analysis_rejects_request_without_analyzable_metrics(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    _create_user(db_session, user_id=1)

    previous_user_override = fastapi_app.dependency_overrides.get(get_current_user)
    fastapi_app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=1)
    try:
        response = client.post(
            "/api/v1/health-metrics/analyses",
            json={
                "sex": "male",
                "metrics": [
                    {
                        "metric_code": "height",
                        "metric_name": "신장",
                        "value": "172.0",
                        "unit": "cm",
                        "raw_text": "172.0",
                    },
                    {
                        "metric_code": "urine_protein",
                        "metric_name": "요단백",
                        "value": "음성",
                        "unit": "",
                        "raw_text": "음성",
                    },
                ],
            },
        )

        assert response.status_code == 422
        assert response.json()["error_code"] == "NO_ANALYZABLE_HEALTH_METRICS"
    finally:
        if previous_user_override is None:
            fastapi_app.dependency_overrides.pop(get_current_user, None)
        else:
            fastapi_app.dependency_overrides[get_current_user] = previous_user_override


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_value_rejected_by_schema(bad_value: float) -> None:
    from pydantic import ValidationError

    from app.domains.health_metric.schemas import HealthMetricInput

    with pytest.raises(ValidationError):
        HealthMetricInput(label="LDL", value=bad_value)


def test_explanation_service_uses_openai_structured_response(monkeypatch) -> None:
    async def fake_call_openai(self, payload):
        assert payload["model"] == "test-model"
        assert payload["text"]["format"]["type"] == "json_schema"
        assert "Do not diagnose disease" in payload["input"][0]["content"]
        return {
            "output_text": """
            {
              "summary": "LDL 수치가 높아 주의 깊게 볼 필요가 있습니다.",
              "highlights": ["LDL은 위험으로 분류되었습니다."],
              "item_explanations": [
                {
                  "canonical_test_code": "LDL",
                  "input_label": "LDL",
                  "title": "LDL",
                  "explanation": "LDL은 혈관 건강과 관련해 확인하는 콜레스테롤입니다.",
                  "status_label": "위험"
                }
              ],
              "disclaimer": "진단이나 치료 지시가 아닙니다."
            }
            """
        }

    monkeypatch.setattr(HealthMetricExplanationService, "_call_openai", fake_call_openai)
    request = HealthMetricEvaluationRequest(
        sex="male",
        metrics=[_metric("LDL", 190)],
    )
    results = HealthMetricService().evaluate_metrics(request)

    import asyncio

    explanation = asyncio.run(
        HealthMetricExplanationService(
            api_key="test-key",
            model="test-model",
        ).build_explanation(request, results)
    )

    assert explanation.status == "generated"
    assert explanation.summary == "LDL 수치가 높아 주의 깊게 볼 필요가 있습니다."
    assert explanation.item_explanations[0].canonical_test_code == "LDL"


def test_explanation_service_falls_back_on_openai_failure(monkeypatch) -> None:
    async def fake_call_openai(self, payload):
        raise RuntimeError("boom")

    monkeypatch.setattr(HealthMetricExplanationService, "_call_openai", fake_call_openai)
    request = HealthMetricEvaluationRequest(
        sex="male",
        metrics=[_metric("중성지방", 510)],
    )
    results = HealthMetricService().evaluate_metrics(request)

    import asyncio

    explanation = asyncio.run(
        HealthMetricExplanationService(api_key="test-key").build_explanation(
            request,
            results,
        )
    )

    assert explanation.status == "fallback"
    assert "위험" in explanation.highlights[0]
    assert explanation.item_explanations[0].status_label == "위험"
