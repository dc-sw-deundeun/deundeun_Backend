from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str | None = None

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 14

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_use_tls: bool = True

    analysis_server_base_url: str | None = None
    analysis_server_api_key: str | None = None
    analysis_callback_secret: str | None = None
    analysis_polling_interval_seconds: int = 60

    clova_ocr_invoke_url: str | None = None
    clova_ocr_secret_key: str | None = None
    ocr_min_confidence: float = 0.8
    ocr_request_timeout_seconds: int = 15
    ocr_max_retries: int = 1
    max_images_per_upload: int = 10
    max_single_upload_size_bytes: int = 10 * 1024 * 1024
    max_total_upload_size_bytes: int = 30 * 1024 * 1024
    ocr_concurrency: int = 5
    ocr_global_concurrency: int = 10
    ocr_acquire_timeout_seconds: float = 1.0
    ocr_retry_after_seconds: int = 10

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env in ("production", "staging"):
            if self.jwt_secret_key == "change-me":
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure value in production/staging"
                )
            if not self.clova_ocr_invoke_url or not self.clova_ocr_secret_key:
                raise ValueError(
                    "CLOVA_OCR_INVOKE_URL and CLOVA_OCR_SECRET_KEY must be configured in production/staging"
                )
        return self


settings = Settings()
