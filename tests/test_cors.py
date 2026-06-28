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


def test_settings_accepts_csv_cors_and_proxy_values() -> None:
    settings = Settings(
        cors_allow_origins="https://www.deundeun.xyz,http://localhost:5173",
        cors_allow_methods="GET,POST,OPTIONS",
        cors_allow_headers="Authorization,Content-Type",
        trusted_proxy_cidrs="172.16.0.0/12,10.0.0.0/8",
    )

    assert settings.cors_allow_origins == [
        "https://www.deundeun.xyz",
        "http://localhost:5173",
    ]
    assert settings.cors_allow_methods == ["GET", "POST", "OPTIONS"]
    assert settings.cors_allow_headers == ["Authorization", "Content-Type"]
    assert settings.trusted_proxy_cidrs == ["172.16.0.0/12", "10.0.0.0/8"]


def test_settings_accepts_json_array_cors_and_proxy_values() -> None:
    settings = Settings(
        cors_allow_origins='["https://www.deundeun.xyz","http://localhost:5173"]',
        trusted_proxy_cidrs='["172.16.0.0/12","10.0.0.0/8"]',
    )

    assert settings.cors_allow_origins == [
        "https://www.deundeun.xyz",
        "http://localhost:5173",
    ]
    assert settings.trusted_proxy_cidrs == ["172.16.0.0/12", "10.0.0.0/8"]
