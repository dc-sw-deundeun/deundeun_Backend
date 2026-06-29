"""LLM provider 설정 검증 테스트 (CodeRabbit #1)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_llm_provider_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        Settings(llm_provider="gpt")  # openai|clova 만 허용


def test_production_requires_clova_key_when_provider_is_clova() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="secure",
            clova_ocr_invoke_url="https://ocr",
            clova_ocr_secret_key="ocr-secret",
            llm_provider="clova",
            clova_studio_api_key=None,
        )


def test_production_requires_openai_key_when_provider_is_openai() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            jwt_secret_key="secure",
            clova_ocr_invoke_url="https://ocr",
            clova_ocr_secret_key="ocr-secret",
            llm_provider="openai",
            openai_api_key=None,
        )
