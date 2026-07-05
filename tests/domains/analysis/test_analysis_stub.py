import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domains.analysis.dependencies import build_analysis_service
from app.domains.analysis.models import AnalysisJob
from app.domains.analysis.repository import AnalysisRepository
from app.domains.analysis.status import AnalysisStatus
from app.domains.mission.policy import local_date_for_timezone
from app.domains.mission.repository import MissionRepository
from app.domains.ocr.status import OcrStatus
from app.domains.onboarding.repository import OnboardingRepository
from app.domains.record.repository import RecordRepository
from app.domains.record.schemas import CommitMetricRequest, ManualCheckupRequest
from app.domains.record.service import RecordService
from app.domains.user.models import OnboardingStep, User
from app.infrastructure.external_analysis.signature import compute_analysis_signature
from tests.conftest import CapturingEmailClient
from tests.test_auth_flow import login_user, signup_user


def _create_user(db_session: Session, *, user_id: int, email: str) -> None:
    user = User(
        id=user_id,
        email=email,
        password_hash="hash",
        nickname="analysis-user",
        onboarding_step=OnboardingStep.INITIAL_CHECKUP.value,
        timezone="Asia/Seoul",
    )
    db_session.add(user)
    db_session.commit()


def _verified_record(db_session: Session, user_id: int) -> int:
    service = RecordService(
        RecordRepository(db_session),
        OnboardingRepository(db_session),
    )
    record = service.create_manual(
        user_id,
        ManualCheckupRequest(
            metrics=[
                CommitMetricRequest(
                    metric_code="fasting_glucose",
                    metric_name="공복혈당",
                    value="126",
                    unit="mg/dL",
                )
            ]
        ),
    )
    repo = RecordRepository(db_session)
    locked = repo.get_record(record.id)
    assert locked is not None
    locked.ocr_status = OcrStatus.COMPLETED.value
    repo.set_verified(locked)
    db_session.commit()
    return record.id


def _auth_headers(
    client: TestClient, email_client: CapturingEmailClient, email: str
) -> dict[str, str]:
    signup_user(client, email_client, email=email, nickname="analysis-user")
    access = login_user(client, email=email).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {access}"}


def _today_kst() -> date:
    return local_date_for_timezone("Asia/Seoul")


def _fake_trigger(triggered: list[int]):
    def _trigger(user_id: int, db) -> bool:
        triggered.append(user_id)
        return True

    return _trigger


def _raising_trigger(user_id: int, db) -> bool:
    raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_stub_analysis_triggers_mission_generation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """분석 완료 시 legacy 기본미션 자동배정 대신 엔진 생성 트리거(#41)가 호출된다."""
    triggered: list[int] = []
    monkeypatch.setattr(
        "app.domains.analysis.service.trigger_checkup_regeneration",
        _fake_trigger(triggered),
    )
    _create_user(db_session, user_id=1, email="stub-analysis@example.com")
    record_id = _verified_record(db_session, user_id=1)
    service = build_analysis_service(db_session)
    result = await service.create_analysis_job(record_id, user_id=1)

    assert result.status == AnalysisStatus.COMPLETED.value
    job_result = service.get_job_result(result.job_id, user_id=1)
    assert job_result.summary is not None
    assert job_result.summary.summary_text

    assert triggered == [1]  # 엔진 생성 트리거로 넘어감
    # legacy 기본미션(DEFAULT_SELF_CHECK)은 더 이상 동기적으로 배정되지 않는다.
    mission_repo = MissionRepository(db_session)
    assert mission_repo.count_user_missions_for_date(user_id=1, assigned_date=_today_kst()) == 0


@pytest.mark.asyncio
async def test_trigger_failure_does_not_break_callback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """미션 생성 트리거가 예기치 않게 실패해도 분석 완료 처리는 best-effort로 보존된다."""
    monkeypatch.setattr(
        "app.domains.analysis.service.trigger_checkup_regeneration", _raising_trigger
    )
    _create_user(db_session, user_id=1, email="trigger-fail@example.com")
    record_id = _verified_record(db_session, user_id=1)
    service = build_analysis_service(db_session)

    result = await service.create_analysis_job(record_id, user_id=1)

    assert result.status == AnalysisStatus.COMPLETED.value
    job_result = service.get_job_result(result.job_id, user_id=1)
    assert job_result.summary is not None


def test_unverified_record_returns_409(
    client: TestClient, db_session: Session, email_client: CapturingEmailClient
) -> None:
    email = "unverified-analysis@example.com"
    headers = _auth_headers(client, email_client, email)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"]

    repo = RecordRepository(db_session)
    record = repo.create_record(user_id, "MANUAL", ocr_status=OcrStatus.COMPLETED.value)
    db_session.commit()

    res = client.post(f"/api/v1/analysis/checkups/{record.id}", headers=headers)
    assert res.status_code == 409
    assert res.json()["error_code"] == "NOT_VERIFIED"


@pytest.mark.asyncio
async def test_duplicate_callback_is_idempotent(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    triggered: list[int] = []
    monkeypatch.setattr(
        "app.domains.analysis.service.trigger_checkup_regeneration",
        _fake_trigger(triggered),
    )
    _create_user(db_session, user_id=1, email="dup-callback@example.com")
    record_id = _verified_record(db_session, user_id=1)
    analysis_repo = AnalysisRepository(db_session)
    analysis_repo.save_job(
        AnalysisJob(
            record_id=record_id,
            user_id=1,
            external_job_id="manual-dup-callback",
            status=AnalysisStatus.PROCESSING.value,
        )
    )
    service = build_analysis_service(db_session)

    callback = service._analysis_client.build_callback_payload(
        external_job_id="manual-dup-callback",
        record_id=record_id,
        metrics=service._build_metric_dtos(record_id),
    )
    service.handle_callback(callback)
    service.handle_callback(callback)

    assert triggered == [1]  # 중복 콜백은 완료된 job에서 조기 반환 → 재트리거 안 함
    assert analysis_repo.find_summary_by_record_id(record_id) is not None


def test_analysis_e2e_via_api(
    client: TestClient, db_session: Session, email_client: CapturingEmailClient
) -> None:
    email = "analysis-e2e@example.com"
    headers = _auth_headers(client, email_client, email)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"]
    record_id = _verified_record(db_session, user_id)

    create_res = client.post(f"/api/v1/analysis/checkups/{record_id}", headers=headers)
    assert create_res.status_code == 200
    job_id = create_res.json()["data"]["job_id"]

    status_res = client.get(f"/api/v1/analysis/jobs/{job_id}", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["data"]["status"] == AnalysisStatus.COMPLETED.value

    result_res = client.get(f"/api/v1/analysis/jobs/{job_id}/result", headers=headers)
    assert result_res.status_code == 200
    assert result_res.json()["data"]["summary"]["risk_level"]


def test_callback_requires_valid_signature(
    client: TestClient, db_session: Session, email_client: CapturingEmailClient
) -> None:
    email = "callback-signature@example.com"
    headers = _auth_headers(client, email_client, email)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["data"]["id"]
    record_id = _verified_record(db_session, user_id)

    create_res = client.post(f"/api/v1/analysis/checkups/{record_id}", headers=headers)
    external_job_id = create_res.json()["data"]["external_job_id"]

    payload = {
        "external_job_id": external_job_id,
        "record_id": record_id,
        "status": "COMPLETED",
        "summary": {
            "risk_level": "GOOD",
            "summary_text": "ok",
        },
        "mission_candidates": [],
    }
    bad_res = client.post("/api/v1/analysis/callback", json=payload)
    assert bad_res.status_code == 403

    body = json.dumps(payload)
    signature = compute_analysis_signature(body, "dev-analysis-callback-secret")
    ok_res = client.post(
        "/api/v1/analysis/callback",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Analysis-Signature": signature,
        },
    )
    assert ok_res.status_code == 200


def test_callback_returns_400_for_malformed_signed_body(client: TestClient) -> None:
    body = b"\xff"
    signature = compute_analysis_signature(body, "dev-analysis-callback-secret")

    res = client.post(
        "/api/v1/analysis/callback",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Analysis-Signature": signature,
        },
    )

    assert res.status_code == 400
    assert res.json()["error_code"] == "INVALID_CALLBACK_PAYLOAD"
