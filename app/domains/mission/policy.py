import logging
import re
from datetime import date, datetime, timedelta, timezone
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
    """미션 타입에 따른 경험치 보상량을 계산합니다(레거시 mock seam용)."""
    return _EXP_BY_TYPE.get(mission_type, _DEFAULT_EXP)


# --- 생성 미션 보상/수행시각 (난이도 기반 EXP + 규칙 기반 수행 시각) -----------------


def xp_for_difficulty(difficulty: int) -> int:
    """난이도 기반 EXP 보상 — difficulty 1→10, 2→20, 3→30 (최소 1로 취급)."""
    return max(1, int(difficulty)) * 10


# when(의미적 시점) 우선 매핑 → HH:MM.
_TIME_BY_WHEN = {
    "기상 후": "07:00",
    "식후": "13:00",
    "취침 전": "22:00",
    "낮 시간": "15:00",
}
# when이 없을 때 mission_type 기반 기본 시각.
_TIME_BY_TYPE = {
    "hydration": "09:00",
    "exercise": "18:00",
    "diet": "12:00",
    "sleep": "22:00",
    "stress": "20:00",
    "habit": "10:00",
    "checkup_followup": "10:00",
}
_DEFAULT_TIME = "12:00"
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def suggested_time(mission_type: str, when: str) -> str:
    """규칙 기반 예상 수행 시각(HH:MM). when(식후 등)을 우선하고, 없으면 타입 기본값."""
    if when in _TIME_BY_WHEN:
        return _TIME_BY_WHEN[when]
    return _TIME_BY_TYPE.get(mission_type, _DEFAULT_TIME)


def normalize_time(candidate: str | None, mission_type: str, when: str) -> str:
    """LLM이 준 수행 시각을 검증 — HH:MM(24h) 형식이면 채택, 아니면 규칙값으로 폴백."""
    if candidate and _TIME_RE.match(candidate.strip()):
        return candidate.strip()
    return suggested_time(mission_type, when)


def week_range_for_date(d: date) -> tuple[date, date]:
    """d가 속한 주의 월요일~일요일 범위(둘 다 포함)."""
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


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


def local_datetime_for_timezone(timezone_name: str | None, *, now: datetime | None = None) -> datetime:
    """local_date_for_timezone와 동일한 폴백 규칙으로 로컬 datetime 반환 (알림 스케줄러용)."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo(timezone_name or _DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("unknown timezone %r; falling back to %s", timezone_name, _DEFAULT_TZ)
        zone = ZoneInfo(_DEFAULT_TZ)
    return current.astimezone(zone)
