import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

# 테이블 등록을 위해 모든 모델을 import 한다.
import app.domains.ocr.models  # noqa: F401
import app.domains.record.models  # noqa: F401
from app.database.base import Base
from app.main import app as fastapi_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(fastapi_app)


@pytest.fixture(scope="session")
def _pg_engine():
    # 테스트 세션당 PostgreSQL 컨테이너 1회 기동 (운영 DB와 동일 dialect).
    with PostgresContainer("postgres:16") as postgres:
        engine = create_engine(postgres.get_connection_url())
        yield engine
        engine.dispose()


@pytest.fixture
def db_session(_pg_engine):
    # 테스트마다 스키마를 새로 만들고 끝나면 drop 해 격리한다.
    Base.metadata.create_all(_pg_engine)
    TestingSession = sessionmaker(bind=_pg_engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(_pg_engine)
