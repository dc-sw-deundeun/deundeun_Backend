import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.exceptions import register_exception_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.database.session import check_db_connection, get_engine

    engine = get_engine()
    if engine is None:
        logger.warning("DATABASE_URL이 설정되지 않았습니다. DB 연결 없이 시작합니다.")
    else:
        try:
            check_db_connection()
            logger.info("DB 연결 확인 완료.")
        except Exception as e:
            logger.warning("DB 연결 실패: %s", e)

    yield

    if engine is not None:
        engine.dispose()
        logger.info("DB 엔진 종료.")


app = FastAPI(
    title="deundeun API",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router)
