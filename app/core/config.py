from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: Optional[str] = None

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    analysis_server_base_url: Optional[str] = None
    analysis_server_api_key: Optional[str] = None
    analysis_callback_secret: Optional[str] = None
    analysis_polling_interval_seconds: int = 60

    clova_ocr_invoke_url: Optional[str] = None
    clova_ocr_secret_key: Optional[str] = None
    ocr_polling_interval_seconds: int = 30
    ocr_min_confidence: float = 0.8
    ocr_request_timeout_seconds: int = 30
    ocr_max_retries: int = 2
    ocr_stuck_timeout_seconds: int = 300
    local_storage_dir: str = "var/ocr_tmp"
    max_upload_size_bytes: int = 10 * 1024 * 1024  # 업로드 결과지 최대 크기(기본 10MB)


settings = Settings()
