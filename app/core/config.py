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


settings = Settings()
