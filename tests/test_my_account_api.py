from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.user.models import User, UserStatus
from tests.conftest import CapturingEmailClient
from tests.test_auth_flow import login_user, signup_user

BASE = "/api/v1/my"


def _auth(
    client: TestClient,
    email_client: CapturingEmailClient,
    *,
    email: str = "my-account@example.com",
    nickname: str = "마이사용자",
) -> dict[str, str]:
    signup_user(client, email_client, email=email, nickname=nickname)
    token = login_user(client, email=email).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_my_profile_requires_auth(client: TestClient) -> None:
    assert client.get(f"{BASE}/profile").status_code == 401
    assert client.patch(f"{BASE}/profile", json={"nickname": "수정"}).status_code == 401
    assert client.delete(f"{BASE}/account").status_code == 401


def test_get_my_profile_returns_current_user(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth(
        client,
        email_client,
        email="my-profile@example.com",
        nickname="프로필사용자",
    )

    res = client.get(f"{BASE}/profile", headers=headers)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["email"] == "my-profile@example.com"
    assert data["nickname"] == "프로필사용자"
    assert data["onboarding_step"] == "CONSENT"
    assert data["status"] == "ACTIVE"


def test_update_my_profile_nickname_reflects_auth_me_and_home(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth(client, email_client, email="my-patch@example.com", nickname="변경전")

    res = client.patch(f"{BASE}/profile", json={"nickname": "변경후"}, headers=headers)

    assert res.status_code == 200
    assert res.json()["data"]["nickname"] == "변경후"

    me_res = client.get("/api/v1/auth/me", headers=headers)
    home_res = client.get("/api/v1/home", headers=headers)

    assert me_res.status_code == 200
    assert me_res.json()["data"]["nickname"] == "변경후"
    assert home_res.status_code == 200
    assert home_res.json()["data"]["user"]["nickname"] == "변경후"


def test_update_my_profile_rejects_empty_body(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth(client, email_client, email="my-empty@example.com")

    res = client.patch(f"{BASE}/profile", json={}, headers=headers)

    assert res.status_code == 400
    assert res.json()["error_code"] == "PROFILE_UPDATE_EMPTY"


def test_update_my_profile_validates_nickname(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth(client, email_client, email="my-invalid@example.com")

    empty = client.patch(f"{BASE}/profile", json={"nickname": ""}, headers=headers)
    too_long = client.patch(f"{BASE}/profile", json={"nickname": "가" * 51}, headers=headers)

    assert empty.status_code == 422
    assert too_long.status_code == 422


def test_delete_my_account_revokes_sessions(
    client: TestClient,
    email_client: CapturingEmailClient,
    db_session: Session,
) -> None:
    email = "my-delete@example.com"
    signup_user(client, email_client, email=email)
    login_data = login_user(client, email=email).json()["data"]
    access = login_data["access_token"]
    refresh = login_data["refresh_token"]
    headers = {"Authorization": f"Bearer {access}"}

    res = client.delete(f"{BASE}/account", headers=headers)

    assert res.status_code == 200
    assert res.json()["message"] == "회원탈퇴가 완료되었습니다."

    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    db_session.refresh(user)
    assert user.status == UserStatus.DELETED
    assert user.token_version == 1

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401

    login_res = login_user(client, email=email)
    assert login_res.status_code == 403
    assert login_res.json()["error_code"] == "ACCOUNT_INACTIVE"
