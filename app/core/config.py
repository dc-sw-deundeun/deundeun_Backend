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

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = 20.0

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env in ("production", "staging") and self.jwt_secret_key == "change-me":
            raise ValueError("JWT_SECRET_KEY must be set to a secure value in production/staging")
        return self


settings = Settings()
