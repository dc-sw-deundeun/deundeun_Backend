from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.domains.health_metric.models  # noqa: F401
import app.domains.auth.models  # noqa: F401
import app.domains.user.models  # noqa: F401
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database.base import Base
from app.database.session import get_db
from app.domains.health_metric.explanation_service import HealthMetricExplanationService
from app.domains.health_metric.schemas import HealthMetricEvaluationRequest
from app.domains.health_metric.service import (
    HealthMetricService,
    build_detail_views,
    build_summary_view,
)
from app.domains.user.schemas import CurrentUser
from app.main import app


def _result_by_code(results, code: str):
    return next(item for item in results if item.canonical_test_code == code)


def test_evaluate_metrics_classifies_normal_caution_and_risk() -> None:
    request = HealthMetricEvaluationRequest(
        sex="male",
        metrics=[
            {"label": "BMI", "value": 22.0},
            {"label": "LDL", "value": 130.0},
            {"label": "중성지방", "value": 510.0},
            {"label": "허리둘레", "value": 92.0},
        ],
    )

    results = HealthMetricService().evaluate_metrics(request)

    assert _result_by_code(results, "BMI").status == "normal"
    assert _result_by_code(results, "LDL").status == "caution"
    tg = _result_by_code(results, "TG")
    assert tg.status == "risk"
    assert tg.note == "매우 높음"
    assert _result_by_code(results, "WAIST").status == "risk"


def test_sex_specific_metric_aliases_override_request_sex() -> None:
    request = HealthMetricEvaluationRequest(
        sex="female",
        metrics=[
            {"label": "HGB_M", "value": 12.9},
            {"label": "GGT_F", "value": 36},
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
        metrics=[{"label": "지원안함", "value": 1.0}],
    )

    result = HealthMetricService().evaluate_metrics(request)[0]

    assert result.status == "unknown"
    assert result.status_label == "판정불가"
    assert result.canonical_test_code is None


def test_endpoint_returns_structured_evaluation_response(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/health-metrics/evaluate",
            json={
                "sex": "male",
                "metrics": [
                    {"label": "공복혈당", "value": 126},
                    {"label": "PHQ9", "value": 8},
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    results = body["data"]["results"]
    assert results[0]["canonical_test_code"] == "FPG"
    assert results[0]["status"] == "risk"
    assert results[1]["canonical_test_code"] == "PHQ9"
    assert results[1]["status"] == "caution"
    assert body["data"]["explanation"]["status"] == "fallback"
    assert body["data"]["explanation"]["summary"]
    assert body["data"]["explanation"]["item_explanations"]
    assert body["data"]["ui"]["summary"]["cards"]
    assert body["data"]["ui"]["details"]


def test_builds_summary_and_detail_view_models() -> None:
    request = HealthMetricEvaluationRequest(
        sex="male",
        metrics=[
            {"label": "LDL", "value": 190},
            {"label": "공복혈당", "value": 110},
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

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/health-metrics/analyses",
            json={"metrics": [{"label": "LDL", "value": 150}]},
        )

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_create_summary_and_detail_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
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

    previous_override = app.dependency_overrides.get(get_db)
    previous_user_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=1)
    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/health-metrics/analyses",
                json={
                    "sex": "male",
                    "metrics": [
                        {"label": "LDL", "value": 190},
                        {"label": "공복혈당", "value": 110},
                    ],
                },
            )
            assert create_response.status_code == 200
            analysis_id = create_response.json()["data"]["analysis_id"]

            summary_response = client.get(
                f"/api/v1/health-metrics/analyses/{analysis_id}/summary"
            )
            detail_response = client.get(
                f"/api/v1/health-metrics/analyses/{analysis_id}/details/LDL"
            )

        assert summary_response.status_code == 200
        assert summary_response.json()["data"]["analysis_id"] == analysis_id
        assert summary_response.json()["data"]["cards"][0]["code"] == "LDL"
        assert "cta" not in summary_response.json()["data"]
        assert detail_response.status_code == 200
        assert detail_response.json()["data"]["metric"]["code"] == "LDL"
        assert detail_response.json()["data"]["meaning"]["body"]

        app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=2)
        with TestClient(app) as client:
            forbidden_summary = client.get(
                f"/api/v1/health-metrics/analyses/{analysis_id}/summary"
            )
        assert forbidden_summary.status_code == 404
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        if previous_user_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous_user_override


def test_detail_endpoint_returns_metric_trend_from_previous_analyses(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
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

    previous_override = app.dependency_overrides.get(get_db)
    previous_user_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=1)
    try:
        with TestClient(app) as client:
            first = client.post(
                "/api/v1/health-metrics/analyses",
                json={
                    "measured_at": "2026-06-25",
                    "metrics": [{"label": "LDL", "value": 150}],
                },
            )
            app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=2)
            other_user = client.post(
                "/api/v1/health-metrics/analyses",
                json={
                    "measured_at": "2026-06-25",
                    "metrics": [{"label": "LDL", "value": 999}],
                },
            )
            app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=1)
            second = client.post(
                "/api/v1/health-metrics/analyses",
                json={
                    "measured_at": "2025-01-01",
                    "metrics": [{"label": "LDL", "value": 170}],
                },
            )
            third = client.post(
                "/api/v1/health-metrics/analyses",
                json={
                    "measured_at": "2026-06-26",
                    "metrics": [{"label": "LDL", "value": 140}],
                },
            )
            analysis_id = third.json()["data"]["analysis_id"]
            detail_response = client.get(
                f"/api/v1/health-metrics/analyses/{analysis_id}/details/LDL"
            )

        assert first.status_code == 200
        assert other_user.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 200
        assert detail_response.status_code == 200
        points = detail_response.json()["data"]["trend"]["points"]
        assert [point["value"] for point in points] == [170.0, 150.0, 140.0]
        assert [point["label"] for point in points] == ["2025.01.01", "06.25", "06.26"]
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override
        if previous_user_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous_user_override


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
        metrics=[{"label": "LDL", "value": 190}],
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
        metrics=[{"label": "중성지방", "value": 510}],
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
