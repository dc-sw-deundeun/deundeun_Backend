"""미션 생성 스케줄러 — 매시 틱으로 유저 로컬 자정 기준 당일 미션을 멱등 생성.

API 없이 백그라운드에서만 동작한다. mission_generation_runs UNIQUE(user_id, generation_date)로
같은 로컬 날짜에 여러 틱이 돌아도 최초 1회만 생성하고 나머지는 claim 실패→스킵한다.
유저별로 세션을 분리해 한 유저의 실패가 다른 유저 생성에 전파되지 않게 한다.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from app.database.session import session_scope
from app.domains.mission.generation_service import MissionGenerationService
from app.domains.mission.timeutil import local_date
from app.domains.pkg.repository import PkgRepository

logger = logging.getLogger(__name__)

_TICK_JOB_ID = "mission_daily_generation"


async def run_daily_generation_tick() -> None:
    """PKG 스냅샷 보유 활성 유저를 훑어 각자 로컬 날짜의 미션을 멱등 생성한다."""
    with session_scope() as db:
        targets = PkgRepository(db).list_snapshot_user_targets()

    generated = 0
    for user_id, tz in targets:
        target_date = local_date(tz)
        try:
            with session_scope() as db:
                created = await MissionGenerationService(db).generate_for_user(
                    user_id, target_date, source="scheduler"
                )
            generated += int(created)
        except Exception:
            logger.warning("daily generation tick failed (user_id=%s)", user_id, exc_info=True)
    logger.info("mission daily tick done: %d/%d users generated", generated, len(targets))


def create_scheduler() -> AsyncIOScheduler:
    """매시 정각에 당일 미션을 생성하는 AsyncIOScheduler를 구성한다(미기동)."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_daily_generation_tick,
        trigger="cron",
        minute=0,  # 매시 정각
        id=_TICK_JOB_ID,
        max_instances=1,  # 틱이 겹치면 이전 실행을 존중(중복 스캔 방지)
        coalesce=True,  # 밀린 실행은 1회로 합침
        replace_existing=True,
    )
    return scheduler
