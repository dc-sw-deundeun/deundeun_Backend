import json

from pydantic import field_validator, model_validator
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
    analysis_client: str = "stub"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = 20.0

    neo4j_uri: str | None = None
    neo4j_user: str | None = None
    neo4j_password: str | None = None

    # 미션 생성 등 LLM 텍스트 경로는 GPT(OpenAI)로 통일. (CLOVA OCR은 별도 서비스로 유지)

    health_metric_analysis_rate_limit_per_minute: int = 10

    # 미션 생성 스케줄러(매시 틱) 기동 여부. test 환경/원치 않는 배포에서 끌 수 있다.
    mission_scheduler_enabled: bool = True

    cors_allow_origins: list[str] | str = []
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] | str = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] | str = ["Authorization", "Content-Type"]

    @field_validator(
        "cors_allow_origins", "cors_allow_methods", "cors_allow_headers", mode="before"
    )
    @classmethod
    def parse_csv_list(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
                return parsed
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    # X-Forwarded-For를 신뢰할 리버스 프록시(nginx 등) 뒤에 배포될 때 True로 설정
    trusted_proxy: bool = False
    # 요청 source IP가 이 CIDR에 포함될 때만 X-Forwarded-For를 신뢰합니다.
    trusted_proxy_cidrs: list[str] | str = []

    @field_validator("trusted_proxy_cidrs", mode="before")
    @classmethod
    def parse_trusted_proxy_cidrs(cls, value):
        return cls.parse_csv_list(value)

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

    media_max_image_size_bytes: int = 5 * 1024 * 1024

    @field_validator("analysis_client")
    @classmethod
    def validate_analysis_client(cls, value: str) -> str:
        if value != "stub":
            raise ValueError(
                "ANALYSIS_CLIENT must be 'stub' until http/openai clients are implemented"
            )
        return value

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
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY must be configured in production/staging")
            if not self.analysis_callback_secret:
                raise ValueError(
                    "ANALYSIS_CALLBACK_SECRET must be configured in production/staging"
                )
        return self


settings = Settings()
