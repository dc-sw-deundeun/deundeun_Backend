from app.core.config import Settings, settings


def test_ocr_settings_defaults():
    assert settings.ocr_min_confidence == 0.8
    assert settings.ocr_request_timeout_seconds == 15
    assert settings.ocr_max_retries == 1
    assert settings.max_images_per_upload == 10
    assert settings.max_total_upload_size_bytes == 30 * 1024 * 1024
    assert settings.ocr_concurrency == 5


def test_clova_secrets_default_to_none(monkeypatch):
    # 시크릿류는 코드 기본값이 None인지 검증한다.
    # .env/실제 환경변수의 영향을 받지 않도록 격리한다.
    monkeypatch.delenv("CLOVA_OCR_INVOKE_URL", raising=False)
    monkeypatch.delenv("CLOVA_OCR_SECRET_KEY", raising=False)
    isolated = Settings(_env_file=None)
    assert isolated.clova_ocr_invoke_url is None
    assert isolated.clova_ocr_secret_key is None
