"""미션 생성 스케줄러 — 매시 틱으로 유저 로컬 자정 기준 당일 미션을 멱등 생성.

API 없이 백그라운드에서만 동작한다. mission_generation_runs UNIQUE(user_id, generation_date)로
같은 로컬 날짜에 여러 틱이 돌아도 최초 1회만 생성하고 나머지는 claim 실패→스킵한다.
유저별로 세션을 분리해 한 유저의 실패가 다른 유저 생성에 전파되지 않게 한다.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from app.database.session import session_scope
from app.domains.mission.generation_service import MissionGenerationService
from app.domains.mission.policy import local_date_for_timezone, local_datetime_for_timezone
from app.domains.mission.repository import MissionRepository
from app.domains.notification.repository import NotificationRepository
from app.domains.notification.service import NotificationService
from app.domains.pkg.repository import PkgRepository

logger = logging.getLogger(__name__)

_TICK_JOB_ID = "mission_daily_generation"
_NOTIFICATION_JOB_ID = "mission_hourly_notification"


async def run_daily_generation_tick() -> None:
    """PKG 스냅샷 보유 활성 유저를 훑어 각자 로컬 날짜의 미션을 멱등 생성한다."""
    with session_scope() as db:
        targets = PkgRepository(db).list_snapshot_user_targets()

    generated = 0
    for user_id, tz in targets:
        target_date = local_date_for_timezone(tz)
        try:
            with session_scope() as db:
                created = await MissionGenerationService(db).generate_for_user(
                    user_id, target_date, source="scheduler"
                )
            generated += int(created)
        except Exception:
            logger.warning("daily generation tick failed (user_id=%s)", user_id, exc_info=True)
    logger.info("mission daily tick done: %d/%d users generated", generated, len(targets))


def run_mission_notification_tick() -> None:
    """매시 정각: 미션 execution.time이 유저 로컬 현재 시각 HH와 일치하면 알림함 레코드를 생성한다.

    - mission_alarm_enabled=false인 유저는 스킵
    - ASSIGNED 상태 미션만 대상 (COMPLETED 제외)
    - execution.time이 비어있거나 2자 미만이면 스킵
    - notify_mission_reminder()가 ON CONFLICT DO NOTHING으로 멱등 보장
    - 유저당 단일 db.commit() (부분 커밋 방지)
    - 한 유저의 실패는 다른 유저에 전파되지 않음
    """
    with session_scope() as db:
        targets = PkgRepository(db).list_snapshot_user_targets()

    notified = 0
    for user_id, tz in targets:
        local_dt = local_datetime_for_timezone(tz)
        local_hour_str = local_dt.strftime("%H")
        local_date = local_dt.date()
        try:
            with session_scope() as db:
                notif_repo = NotificationRepository(db)
                pref = notif_repo.find_preference_by_user_id(user_id)
                if pref is not None and not pref.mission_alarm_enabled:
                    continue
                rows = MissionRepository(db).list_for_date_with_template(user_id, local_date)
                notif_svc = NotificationService(notif_repo)
                for mission, template in rows:
                    if mission.status != "ASSIGNED":
                        continue
                    exec_time: str = (mission.payload or {}).get("execution", {}).get("time", "")
                    if not exec_time or len(exec_time) < 2 or exec_time[:2] != local_hour_str:
                        continue
                    title = (
                        template.title if template else (mission.payload or {}).get("title", "")
                    ) or "오늘의 미션"
                    body = f"{exec_time} 예정 — 지금 확인해보세요."
                    notif_svc.notify_mission_reminder(
                        user_id=user_id,
                        mission_id=mission.id,
                        title=title,
                        body=body,
                        commit=False,
                    )
                    notified += 1
                db.commit()
        except Exception:
            logger.warning("mission notification tick failed (user_id=%s)", user_id, exc_info=True)
    logger.info("mission notification tick done: %d notifications ensured", notified)


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
    scheduler.add_job(
        run_mission_notification_tick,
        trigger="cron",
        minute=0,
        id=_NOTIFICATION_JOB_ID,
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler
