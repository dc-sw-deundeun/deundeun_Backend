"""미션 도메인 시간 헬퍼 — 유저 timezone 기준 로컬 '오늘' 계산.

스케줄러(생성)와 GET /today(조회)가 동일한 규칙으로 로컬 날짜를 계산해야 생성분과
조회분이 맞물린다. 알 수 없는 timezone은 기본 서울로 폴백한다.
"""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_TZ = "Asia/Seoul"


def local_date(tz: str | None) -> date:
    """주어진 timezone의 현재 로컬 날짜."""
    try:
        zone = ZoneInfo(tz or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("unknown timezone %r; falling back to %s", tz, DEFAULT_TZ)
        zone = ZoneInfo(DEFAULT_TZ)
    return datetime.now(zone).date()
