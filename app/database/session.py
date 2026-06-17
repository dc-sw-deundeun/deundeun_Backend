from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# DATABASE_URL 미설정 시 engine 생성을 skip합니다 (health check만 동작).
_engine = None
_SessionLocal = None

if settings.database_url:
    _engine = create_engine(settings.database_url, pool_pre_ping=True)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI Depends()용 DB 세션 generator입니다. DB 확정 후 활성화됩니다."""
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
