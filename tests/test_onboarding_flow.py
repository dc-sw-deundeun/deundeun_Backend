"""Phase 2 온보딩 플로우 통합 테스트.

흐름: CONSENT → (약관 동의) → WEARABLE → (CONNECT/SKIP) → INITIAL_CHECKUP
     → (Phase 3 검증으로 CHECKUP_VERIFIED) → (complete) → COMPLETED
"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.onboarding import policy as onboarding_policy
from app.domains.onboarding.models import WearableConnection
from app.domains.user.models import OnboardingStep, User
from tests.conftest import CapturingEmailClient
from tests.test_auth_flow import login_user, signup_user

AUTH = "/api/v1/auth"
ONB = "/api/v1/onboarding"

_FULL_CONSENTS = [
    {"consent_type": "TERMS_OF_SERVICE", "version": "1.0", "agreed": True},
    {"consent_type": "PRIVACY", "version": "1.0", "agreed": True},
    {"consent_type": "HEALTH_DATA", "version": "1.0", "agreed": True},
]


def _auth_headers(client: TestClient, email_client: CapturingEmailClient, email: str) -> dict:
    signup_user(client, email_client, email=email)
    access = login_user(client, email=email).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {access}"}


def _set_step(db_session: Session, email: str, step: OnboardingStep) -> None:
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.onboarding_step = step.value
    db_session.commit()


def test_agree_policies_advances_to_wearable(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "consent@example.com")

    res = client.post(f"{AUTH}/policies/agree", json={"consents": _FULL_CONSENTS}, headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["onboarding_step"] == "WEARABLE"

    me = client.get(f"{AUTH}/me", headers=headers).json()["data"]
    assert me["onboarding_step"] == "WEARABLE"


def test_agree_policies_missing_required_consent_returns_400(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "missing@example.com")

    res = client.post(
        f"{AUTH}/policies/agree",
        json={
            "consents": [
                {"consent_type": "TERMS_OF_SERVICE", "version": "1.0", "agreed": True},
                {"consent_type": "PRIVACY", "version": "1.0", "agreed": True},
            ]
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert res.json()["error_code"] == "CONSENT_REQUIRED"


def test_agree_policies_not_agreed_returns_400(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "notagreed@example.com")
    consents = [dict(c) for c in _FULL_CONSENTS]
    consents[2]["agreed"] = False

    res = client.post(f"{AUTH}/policies/agree", json={"consents": consents}, headers=headers)
    assert res.status_code == 400
    assert res.json()["error_code"] == "CONSENT_REQUIRED"


def test_agree_policies_version_mismatch_returns_400(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "stale@example.com")
    consents = [dict(c) for c in _FULL_CONSENTS]
    consents[0]["version"] = "0.9"

    res = client.post(f"{AUTH}/policies/agree", json={"consents": consents}, headers=headers)
    assert res.status_code == 400
    assert res.json()["error_code"] == "POLICY_VERSION_MISMATCH"


def test_agree_policies_duplicate_consent_type_returns_422(
    client: TestClient, email_client: CapturingEmailClient, db_session: Session
) -> None:
    email = "duplicate-consent@example.com"
    headers = _auth_headers(client, email_client, email)
    consents = [
        {"consent_type": "TERMS_OF_SERVICE", "version": "1.0", "agreed": False},
        {"consent_type": "TERMS_OF_SERVICE", "version": "1.0", "agreed": True},
        {"consent_type": "PRIVACY", "version": "1.0", "agreed": True},
        {"consent_type": "HEALTH_DATA", "version": "1.0", "agreed": True},
    ]

    res = client.post(f"{AUTH}/policies/agree", json={"consents": consents}, headers=headers)

    assert res.status_code == 422
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    assert user.onboarding_step == OnboardingStep.CONSENT


def test_agree_policies_twice_returns_409_invalid_step(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "twice@example.com")

    assert (
        client.post(
            f"{AUTH}/policies/agree", json={"consents": _FULL_CONSENTS}, headers=headers
        ).status_code
        == 200
    )
    res = client.post(f"{AUTH}/policies/agree", json={"consents": _FULL_CONSENTS}, headers=headers)
    assert res.status_code == 409
    assert res.json()["error_code"] == "INVALID_ONBOARDING_STEP"


def test_wearable_connect_apple_health_advances_step(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "apple@example.com")
    client.post(f"{AUTH}/policies/agree", json={"consents": _FULL_CONSENTS}, headers=headers)

    res = client.post(
        f"{ONB}/wearable",
        json={
            "action": "CONNECT",
            "provider": "APPLE_HEALTH",
            "scopes": ["steps", "heart_rate"],
        },
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["onboarding_step"] == "INITIAL_CHECKUP"
    assert data["connection"]["provider"] == "APPLE_HEALTH"
    assert data["connection"]["status"] == "CONNECTED"
    assert data["connection"]["scopes"] == ["steps", "heart_rate"]

    status = client.get(f"{ONB}/status", headers=headers).json()["data"]
    assert status["onboarding_step"] == "INITIAL_CHECKUP"
    assert len(status["wearable_connections"]) == 1
    assert status["wearable_connections"][0]["provider"] == "APPLE_HEALTH"


def test_wearable_connect_same_provider_updates_existing_connection(
    client: TestClient, email_client: CapturingEmailClient, db_session: Session
) -> None:
    email = "reconnect@example.com"
    headers = _auth_headers(client, email_client, email)
    client.post(f"{AUTH}/policies/agree", json={"consents": _FULL_CONSENTS}, headers=headers)
    first_res = client.post(
        f"{ONB}/wearable",
        json={
            "action": "CONNECT",
            "provider": "APPLE_HEALTH",
            "scopes": ["steps"],
        },
        headers=headers,
    )
    assert first_res.status_code == 200
    assert first_res.json()["data"]["connection"]["scopes"] == ["steps"]
    _set_step(db_session, email, OnboardingStep.WEARABLE)

    res = client.post(
        f"{ONB}/wearable",
        json={
            "action": "CONNECT",
            "provider": "APPLE_HEALTH",
            "scopes": ["steps", "heart_rate"],
        },
        headers=headers,
    )

    assert res.status_code == 200
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    connections = list(
        db_session.scalars(select(WearableConnection).where(WearableConnection.user_id == user.id))
    )
    assert len(connections) == 1
    assert connections[0].scopes == ["steps", "heart_rate"]


def test_wearable_skip_advances_without_connection(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "skip@example.com")
    client.post(f"{AUTH}/policies/agree", json={"consents": _FULL_CONSENTS}, headers=headers)

    res = client.post(f"{ONB}/wearable", json={"action": "SKIP"}, headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["onboarding_step"] == "INITIAL_CHECKUP"
    assert data["connection"] is None

    status = client.get(f"{ONB}/status", headers=headers).json()["data"]
    assert status["wearable_connections"] == []


def test_wearable_connect_without_provider_returns_422(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "noprovider@example.com")
    client.post(f"{AUTH}/policies/agree", json={"consents": _FULL_CONSENTS}, headers=headers)

    res = client.post(f"{ONB}/wearable", json={"action": "CONNECT"}, headers=headers)
    assert res.status_code == 422


def test_wearable_before_consent_returns_409(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "premature@example.com")

    res = client.post(f"{ONB}/wearable", json={"action": "SKIP"}, headers=headers)
    assert res.status_code == 409
    assert res.json()["error_code"] == "INVALID_ONBOARDING_STEP"


def test_complete_before_checkup_verified_returns_409(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "early@example.com")
    client.post(f"{AUTH}/policies/agree", json={"consents": _FULL_CONSENTS}, headers=headers)
    client.post(f"{ONB}/wearable", json={"action": "SKIP"}, headers=headers)

    res = client.post(f"{ONB}/complete", headers=headers)
    assert res.status_code == 409
    assert res.json()["error_code"] == "ONBOARDING_INCOMPLETE"


def test_complete_after_checkup_verified(
    client: TestClient, email_client: CapturingEmailClient, db_session: Session
) -> None:
    email = "complete@example.com"
    headers = _auth_headers(client, email_client, email)
    _set_step(db_session, email, OnboardingStep.CHECKUP_VERIFIED)

    res = client.post(f"{ONB}/complete", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["onboarding_step"] == "COMPLETED"

    # 이미 완료 → 재요청 시 409
    res2 = client.post(f"{ONB}/complete", headers=headers)
    assert res2.status_code == 409
    assert res2.json()["error_code"] == "ONBOARDING_ALREADY_COMPLETED"


def test_onboarding_status_requires_auth(client: TestClient) -> None:
    res = client.get(f"{ONB}/status")
    assert res.status_code == 401


def test_onboarding_checkup_requires_auth(client: TestClient) -> None:
    res = client.post(f"{ONB}/checkup")
    assert res.status_code == 401


def test_ensure_step_accepts_enum_member() -> None:
    onboarding_policy.ensure_step(OnboardingStep.WEARABLE, OnboardingStep.WEARABLE)
