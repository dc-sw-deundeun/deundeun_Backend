"""Phase 1 인증 플로우 통합 테스트 (TC-002, TC-003, TC-018, 잠금, 블랙리스트)."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.auth.models import EmailVerification
from tests.conftest import CapturingEmailClient

DEFAULT_PASSWORD = "Passw0rd!"
BASE = "/api/v1/auth"


def _request_code(client: TestClient, email: str, purpose: str = "SIGNUP"):
    return client.post(f"{BASE}/email/verify/request", json={"email": email, "purpose": purpose})


def _confirm_code(client: TestClient, email: str, code: str, purpose: str = "SIGNUP"):
    return client.post(
        f"{BASE}/email/verify/confirm",
        json={"email": email, "code": code, "purpose": purpose},
    )


def signup_user(
    client: TestClient,
    email_client: CapturingEmailClient,
    email: str = "user@example.com",
    password: str = DEFAULT_PASSWORD,
    nickname: str = "든든이",
):
    _request_code(client, email)
    code = email_client.codes[email]
    token = _confirm_code(client, email, code).json()["data"]["verification_token"]
    return client.post(
        f"{BASE}/signup",
        json={
            "email": email,
            "password": password,
            "nickname": nickname,
            "verification_token": token,
        },
    )


def login_user(
    client: TestClient, email: str = "user@example.com", password: str = DEFAULT_PASSWORD
):
    return client.post(f"{BASE}/login", json={"email": email, "password": password})


def test_signup_login_me_e2e(client: TestClient, email_client: CapturingEmailClient) -> None:
    signup_res = signup_user(client, email_client, email="e2e@example.com")
    assert signup_res.status_code == 200
    assert signup_res.json()["data"]["user"]["email"] == "e2e@example.com"

    login_res = login_user(client, email="e2e@example.com")
    assert login_res.status_code == 200
    access = login_res.json()["data"]["access_token"]

    me_res = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access}"})
    assert me_res.status_code == 200
    assert me_res.json()["data"]["email"] == "e2e@example.com"
    assert me_res.json()["data"]["onboarding_step"] == "CONSENT"


def test_signup_with_weak_password_returns_400(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    res = signup_user(client, email_client, email="weak@example.com", password="weakpass")
    assert res.status_code == 400
    assert res.json()["error_code"] == "WEAK_PASSWORD"


def test_duplicate_signup_returns_409(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    signup_user(client, email_client, email="dup@example.com")
    # 이미 가입된 이메일로 인증 코드 재요청 → 409
    res = _request_code(client, "dup@example.com")
    assert res.status_code == 409
    assert res.json()["error_code"] == "EMAIL_ALREADY_EXISTS"


def test_login_wrong_password_returns_401(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    signup_user(client, email_client, email="wp@example.com")
    res = login_user(client, email="wp@example.com", password="WrongPass1!")
    assert res.status_code == 401
    assert res.json()["error_code"] == "INVALID_CREDENTIALS"


# --- TC-002: 인증 코드 만료·오입력·재전송 ---
def test_tc002_expired_code_rejected(
    client: TestClient, email_client: CapturingEmailClient, db_session: Session
) -> None:
    _request_code(client, "exp@example.com")
    code = email_client.codes["exp@example.com"]

    verification = db_session.scalar(
        select(EmailVerification).where(EmailVerification.email == "exp@example.com")
    )
    assert verification is not None
    verification.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    res = _confirm_code(client, "exp@example.com", code)
    assert res.status_code == 400
    assert res.json()["error_code"] == "VERIFICATION_CODE_EXPIRED"


def test_tc002_wrong_code_increments_and_locks_attempts(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    _request_code(client, "att@example.com")

    for _ in range(5):
        res = _confirm_code(client, "att@example.com", "000000")
        assert res.status_code == 400
        assert res.json()["error_code"] == "INVALID_VERIFICATION_CODE"

    res = _confirm_code(client, "att@example.com", "000000")
    assert res.status_code == 429
    assert res.json()["error_code"] == "VERIFICATION_ATTEMPTS_EXCEEDED"


def test_tc002_resend_cooldown(client: TestClient, email_client: CapturingEmailClient) -> None:
    assert _request_code(client, "cd@example.com").status_code == 200
    res = _request_code(client, "cd@example.com")
    assert res.status_code == 429
    assert res.json()["error_code"] == "RESEND_TOO_SOON"
    assert res.json()["data"]["retry_after_seconds"] > 0


# --- TC-003: refresh 토큰 재발급·회전 ---
def test_tc003_refresh_rotation(client: TestClient, email_client: CapturingEmailClient) -> None:
    signup_user(client, email_client, email="rt@example.com")
    login_data = login_user(client, email="rt@example.com").json()["data"]
    refresh1 = login_data["refresh_token"]

    refresh_res = client.post(f"{BASE}/refresh", json={"refresh_token": refresh1})
    assert refresh_res.status_code == 200
    access2 = refresh_res.json()["data"]["access_token"]

    me_res = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access2}"})
    assert me_res.status_code == 200

    # 회전된(폐기된) refresh 재사용 → 거부
    reuse_res = client.post(f"{BASE}/refresh", json={"refresh_token": refresh1})
    assert reuse_res.status_code == 401
    assert reuse_res.json()["error_code"] == "INVALID_TOKEN"


# --- TC-018: 비밀번호 재설정 후 refresh·access 무효 ---
def test_tc018_password_reset_revokes_sessions(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    signup_user(client, email_client, email="pr@example.com")
    login_data = login_user(client, email="pr@example.com").json()["data"]
    access1 = login_data["access_token"]
    refresh1 = login_data["refresh_token"]

    assert (
        client.post(f"{BASE}/password/reset/request", json={"email": "pr@example.com"}).status_code
        == 200
    )
    reset_code = email_client.codes["pr@example.com"]
    confirm_res = client.post(
        f"{BASE}/password/reset/confirm",
        json={
            "email": "pr@example.com",
            "code": reset_code,
            "new_password": "NewPass1!",
        },
    )
    assert confirm_res.status_code == 200

    # 기존 refresh 무효
    assert client.post(f"{BASE}/refresh", json={"refresh_token": refresh1}).status_code == 401
    # 기존 access 무효 (token_version 증가)
    me_res = client.get(f"{BASE}/me", headers={"Authorization": f"Bearer {access1}"})
    assert me_res.status_code == 401

    # 새 비밀번호로 로그인 가능
    assert login_user(client, email="pr@example.com", password="NewPass1!").status_code == 200


# --- 로그아웃 access token 블랙리스트 ---
def test_logout_blacklists_access_token(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    signup_user(client, email_client, email="lo@example.com")
    login_data = login_user(client, email="lo@example.com").json()["data"]
    access = login_data["access_token"]
    refresh = login_data["refresh_token"]
    headers = {"Authorization": f"Bearer {access}"}

    assert client.get(f"{BASE}/me", headers=headers).status_code == 200

    logout_res = client.post(f"{BASE}/logout", json={"refresh_token": refresh}, headers=headers)
    assert logout_res.status_code == 200

    # 블랙리스트된 access token으로 접근 → 401
    assert client.get(f"{BASE}/me", headers=headers).status_code == 401
    # 폐기된 refresh 재발급 → 401
    assert client.post(f"{BASE}/refresh", json={"refresh_token": refresh}).status_code == 401


# --- FR-AUTH-008: 로그인 실패 잠금 ---
def test_fr_auth_008_login_lockout(client: TestClient, email_client: CapturingEmailClient) -> None:
    signup_user(client, email_client, email="lock@example.com")

    for _ in range(5):
        res = login_user(client, email="lock@example.com", password="WrongPass1!")
        assert res.status_code == 401

    locked_res = login_user(client, email="lock@example.com", password="WrongPass1!")
    assert locked_res.status_code == 423
    assert locked_res.json()["error_code"] == "ACCOUNT_LOCKED"
    assert locked_res.json()["data"]["retry_after_seconds"] > 0

    # 잠금 중에는 올바른 비밀번호도 거부
    assert login_user(client, email="lock@example.com").status_code == 423
