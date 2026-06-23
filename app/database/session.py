from collections.abc import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine | None:
    """현재 초기화된 SQLAlchemy Engine을 반환합니다."""
    return _engine


def init_db(database_url: str | None = None) -> None:
    """Engine과 SessionLocal을 초기화합니다.

    lifespan / testcontainers fixture에서 명시적으로 호출하거나,
    모듈 임포트 시 DATABASE_URL이 있으면 자동 초기화합니다.
    """
    global _engine, _SessionLocal
    url = database_url or settings.database_url
    if url:
        _engine = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def check_db_connection() -> bool:
    """DB 연결 확인 (lifespan startup 헬스체크용)."""
    if _engine is None:
        return False
    with _engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


def get_db() -> Generator[Session, None, None]:
    """FastAPI Depends()용 DB 세션 generator입니다."""
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 모듈 임포트 시 DATABASE_URL이 있으면 자동 초기화
init_db()
