from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.cors import configure_cors


def _app_with_cors(origins: list[str]) -> FastAPI:
    app = FastAPI()
    settings = Settings(cors_allow_origins=origins)
    configure_cors(app, settings)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


def test_cors_preflight_allows_configured_origin() -> None:
    client = TestClient(_app_with_cors(["https://frontend.example.com"]))

    response = client.options(
        "/ping",
        headers={
            "Origin": "https://frontend.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://frontend.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_preflight_rejects_unconfigured_origin() -> None:
    client = TestClient(_app_with_cors(["https://frontend.example.com"]))

    response = client.options(
        "/ping",
        headers={
            "Origin": "https://other.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
