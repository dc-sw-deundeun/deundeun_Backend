from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str | None = None

    jwt_secret_key: str
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

    health_metric_evaluate_rate_limit_per_minute: int = 20
    health_metric_analysis_rate_limit_per_minute: int = 10

    # X-Forwarded-For를 신뢰할 리버스 프록시(nginx 등) 뒤에 배포될 때 True로 설정
    trusted_proxy: bool = False


settings = Settings()
