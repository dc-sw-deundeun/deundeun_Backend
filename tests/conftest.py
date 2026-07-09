import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from alembic.config import Config

# 테스트 간 격리를 위해 비우는 애플리케이션 테이블 목록(인증 + OCR/검진).
_APP_TABLES = (
    "access_token_blacklist",
    "refresh_tokens",
    "email_verifications",
    "consent_histories",
    "notifications",
    "image_assets",
    "character_owned_animals",
    "character_growth_logs",
    "character_profiles",
    "wearable_connections",
    "pkg_snapshots",
    "mission_generation_runs",
    "users",
    "health_metric_analyses",
    "analysis_mission_candidates",
    "checkup_analysis_summaries",
    "analysis_jobs",
    "user_missions",
    "ocr_jobs",
    "checkup_metric_results",
    "checkup_files",
    "checkup_records",
    "meal_records",
)


class CapturingEmailClient:
    """테스트용 이메일 클라이언트 — 발송된 인증 코드를 메모리에 보관한다."""

    def __init__(self) -> None:
        self.codes: dict[str, str] = {}

    async def send_verification_email(self, to: str, code: str) -> None:
        self.codes[to] = code

    async def send_password_reset_email(self, to: str, code: str) -> None:
        self.codes[to] = code

    async def send_email(self, to: str, subject: str, body_html: str) -> None:
        pass


def _upgrade_alembic(url: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def _truncate_app_tables(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def db_url() -> Generator[str, None, None]:
    """명시된 DATABASE_URL을 우선 사용하고, 없으면 로컬 testcontainers를 사용합니다."""
    if database_url := os.environ.get("DATABASE_URL"):
        yield database_url
        return

    try:
        from testcontainers.postgres import PostgresContainer  # type: ignore[import]
    except ImportError:
        pytest.skip("testcontainers 미설치 — pip install -r requirements-dev.txt")

    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def db_engine(db_url: str) -> Generator[Engine, None, None]:
    import app.core.config as config_module
    import app.database.session as session_module

    config_module.settings.app_env = "test"
    config_module.settings.database_url = db_url
    session_module.init_db(db_url)

    engine = session_module.get_engine()
    if engine is None:
        raise RuntimeError("Failed to initialize database engine")
    _upgrade_alembic(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def email_client() -> CapturingEmailClient:
    return CapturingEmailClient()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """테스트에서 DB를 직접 조작하기 위한 세션.

    각 테스트 종료 시 애플리케이션 테이블을 비워 테스트 간 격리를 보장한다.
    """
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        _truncate_app_tables(db_engine)


@pytest.fixture
def client(
    db_engine: Engine, email_client: CapturingEmailClient
) -> Generator[TestClient, None, None]:
    import app.core.config as config_module
    import app.database.session as session_module
    from app.core.dependencies import get_db, get_email_client_dep
    from app.main import app

    _orig_engine = session_module._engine
    _orig_session = session_module._SessionLocal
    _prev_get_db = app.dependency_overrides.get(get_db)
    _prev_email_dep = app.dependency_overrides.get(get_email_client_dep)
    _orig_analysis_callback_secret = config_module.settings.analysis_callback_secret
    _orig_analysis_client = config_module.settings.analysis_client

    try:
        session_module._engine = db_engine
        _TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session_module._SessionLocal = _TestSession

        config_module.settings.analysis_callback_secret = "dev-analysis-callback-secret"
        config_module.settings.analysis_client = "stub"

        def override_get_db() -> Generator[Session, None, None]:
            db = _TestSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_email_client_dep] = lambda: email_client

        with TestClient(app) as c:
            yield c
    finally:
        if _prev_get_db is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = _prev_get_db
        if _prev_email_dep is None:
            app.dependency_overrides.pop(get_email_client_dep, None)
        else:
            app.dependency_overrides[get_email_client_dep] = _prev_email_dep
        config_module.settings.analysis_callback_secret = _orig_analysis_callback_secret
        config_module.settings.analysis_client = _orig_analysis_client
        session_module._engine = _orig_engine
        session_module._SessionLocal = _orig_session
        _truncate_app_tables(db_engine)
