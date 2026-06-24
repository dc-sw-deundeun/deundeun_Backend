"""주기적 작업 스케줄러입니다. APScheduler AsyncIOScheduler로 구현합니다."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.database.session import session_scope
from app.domains.ocr.dependencies import build_ocr_service
from app.domains.ocr.repository import OcrRepository
from app.domains.record.repository import RecordRepository
from app.workers.ocr_worker import run_ocr_batch

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _ocr_batch_tick() -> int:
    with session_scope() as db:
        service = build_ocr_service(db)
        return await run_ocr_batch(
            service,
            OcrRepository(db),
            RecordRepository(db),
            settings.ocr_stuck_timeout_seconds,
        )


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _ocr_batch_tick,
        "interval",
        seconds=settings.ocr_polling_interval_seconds,
        max_instances=1,
        id="ocr_batch",
    )
    _scheduler.start()
    logger.info("scheduler_started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
