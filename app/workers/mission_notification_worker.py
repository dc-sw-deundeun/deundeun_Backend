"""미션 관련 알림 워커입니다."""


async def send_today_mission_notification() -> None:
    """오늘의 미션 알림을 발송합니다."""
    raise NotImplementedError


async def send_incomplete_mission_notification() -> None:
    """미션 미완료 알림을 발송합니다."""
    raise NotImplementedError


async def send_weekly_mission_report() -> None:
    """주간 미션 리포트 알림을 발송합니다."""
    raise NotImplementedError
