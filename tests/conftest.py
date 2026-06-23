import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from alembic.config import Config


def _upgrade_alembic(url: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


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

    config_module.settings.database_url = db_url
    session_module.init_db(db_url)

    engine = session_module.get_engine()
    if engine is None:
        raise RuntimeError("Failed to initialize database engine")
    _upgrade_alembic(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def client(db_engine: Engine) -> Generator[TestClient, None, None]:
    import app.database.session as session_module
    from app.core.dependencies import get_db
    from app.main import app

    _orig_engine = session_module._engine
    _orig_session = session_module._SessionLocal

    session_module._engine = db_engine
    _TestSession = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session_module._SessionLocal = _TestSession

    def override_get_db() -> Generator[Session, None, None]:
        db = _TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    session_module._engine = _orig_engine
    session_module._SessionLocal = _orig_session
