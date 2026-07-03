import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.cors import configure_cors
from app.core.exceptions import register_exception_handlers
from app.core.openapi import _OPENAPI_TAGS, configure_openapi

if settings.app_env == "development":
    logging.basicConfig(level=logging.INFO)

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

    scheduler = _start_mission_scheduler(engine)

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        logger.info("미션 스케줄러 종료.")
    if engine is not None:
        engine.dispose()
        logger.info("DB 엔진 종료.")


def _start_mission_scheduler(engine):
    """미션 생성 스케줄러를 기동한다. DB 없음/test 환경/비활성 설정이면 건너뛴다."""
    if engine is None or settings.app_env == "test" or not settings.mission_scheduler_enabled:
        return None
    from app.domains.mission.scheduler import create_scheduler

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("미션 생성 스케줄러 기동(매시 틱).")
    return scheduler


app = FastAPI(
    title="deundeun API",
    version="0.1.0",
    description="든든 건강미션 앱 백엔드 API",
    lifespan=lifespan,
    openapi_tags=_OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "persistAuthorization": True,
        "docExpansion": "list",
        "filter": True,
        "tryItOutEnabled": True,
    },
)

configure_openapi(app)
configure_cors(app, settings)
register_exception_handlers(app)


@app.get(
    "/health",
    tags=["Health"],
    summary="[서버/내부] 서버 상태 확인",
    description="로드밸런서, 배포 스크립트, 운영자가 사용하는 health check입니다. 프론트 화면 구현 대상이 아닙니다.",
)
async def health_check():
    return {"status": "ok"}


from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router)
