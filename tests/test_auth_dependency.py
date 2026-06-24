"""GET /api/v1/auth/me 인증 의존성 테스트."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.domains.user.models import User


def _create_user(db_session: Session, email: str = "dep@example.com") -> User:
    user = User(
        email=email,
        password_hash=hash_password("Passw0rd!"),
        nickname="든든이",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_get_me_no_token_returns_401(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH_REQUIRED"


def test_get_me_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_TOKEN"


def test_get_me_refresh_token_rejected(client: TestClient, db_session: Session) -> None:
    from app.core.security import create_refresh_token

    user = _create_user(db_session, email="refreshtype@example.com")
    token = create_refresh_token(subject=user.id)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_TOKEN"


def test_get_me_valid_token_returns_200(client: TestClient, db_session: Session) -> None:
    user = _create_user(db_session, email="valid@example.com")
    token = create_access_token(subject=user.id, token_version=user.token_version)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["id"] == user.id
    assert response.json()["data"]["email"] == "valid@example.com"
