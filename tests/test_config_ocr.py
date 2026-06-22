from app.core.config import settings


def test_ocr_settings_defaults():
    assert settings.ocr_polling_interval_seconds == 30
    assert settings.ocr_min_confidence == 0.8
    assert settings.ocr_request_timeout_seconds == 30
    assert settings.ocr_max_retries == 2
    assert settings.ocr_stuck_timeout_seconds == 300
    # 시크릿류는 기본 None
    assert settings.clova_ocr_invoke_url is None
    assert settings.clova_ocr_secret_key is None
