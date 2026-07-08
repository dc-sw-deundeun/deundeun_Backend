"""LLM 설정 검증 테스트 — GPT(OpenAI)로 통일."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_openai_key() -> None:
    # LLM은 GPT로 통일 — 프로덕션/스테이징은 OPENAI_API_KEY가 반드시 있어야 한다.
    # openai_api_key 외 다른 필수값은 모두 채워, 실패 원인이 openai 키임을 분명히 한다.
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="secure",
            clova_ocr_invoke_url="https://ocr",
            clova_ocr_secret_key="ocr-secret",
            analysis_callback_secret="cb-secret",
            openai_api_key=None,
        )


def test_production_passes_with_openai_key() -> None:
    settings = Settings(
        app_env="production",
        jwt_secret_key="secure",
        clova_ocr_invoke_url="https://ocr",
        clova_ocr_secret_key="ocr-secret",
        openai_api_key="sk-test",
        analysis_callback_secret="cb-secret",
    )
    assert settings.openai_api_key == "sk-test"
