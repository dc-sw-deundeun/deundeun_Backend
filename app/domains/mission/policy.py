import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

_DEFAULT_TZ = "Asia/Seoul"


def can_complete_mission(user_mission) -> bool:
    """미션 완료 가능 여부를 확인합니다."""
    raise NotImplementedError


def can_manually_complete(user_mission) -> bool:
    """수동 완료 가능 여부를 확인합니다."""
    raise NotImplementedError


# 미션 타입별 기본 경험치 보상
_EXP_BY_TYPE = {
    "diet": 15,
    "exercise": 20,
    "hydration": 10,
    "sleep": 15,
    "stress": 10,
    "checkup_followup": 25,
    "habit": 10,
}
_DEFAULT_EXP = 10


def calculate_exp_reward(mission_type: str) -> int:
    """미션 타입에 따른 경험치 보상량을 계산합니다."""
    return _EXP_BY_TYPE.get(mission_type, _DEFAULT_EXP)


def calculate_weekly_statistics(user_missions: list) -> dict:
    """주간 미션 통계를 계산합니다."""
    raise NotImplementedError


def local_date_for_timezone(timezone_name: str | None, *, now: datetime | None = None) -> date:
    """주어진 timezone의 로컬 날짜. None/알 수 없는 tz는 기본 서울로 폴백한다.

    미션 생성(스케줄러)과 조회(GET /today)가 동일 규칙으로 '오늘'을 계산해야 맞물린다.
    """
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo(timezone_name or _DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("unknown timezone %r; falling back to %s", timezone_name, _DEFAULT_TZ)
        zone = ZoneInfo(_DEFAULT_TZ)
    return current.astimezone(zone).date()
