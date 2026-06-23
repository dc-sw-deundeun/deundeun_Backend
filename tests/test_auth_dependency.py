"""GET /api/v1/auth/me 인증 의존성 테스트."""

from fastapi.testclient import TestClient

from app.core.security import create_access_token


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


def test_get_me_valid_token_returns_200(client: TestClient) -> None:
    token = create_access_token(subject=42)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["user_id"] == 42
