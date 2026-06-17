"""검진 기록 관련 알림 워커입니다."""


async def send_checkup_reminder() -> None:
    """검진 등록 주기 알림을 발송합니다."""
    raise NotImplementedError


async def send_wearable_sync_failure_notification() -> None:
    """웨어러블 자동 등록 실패 알림을 발송합니다."""
    raise NotImplementedError


async def send_health_update_request() -> None:
    """건강 기록 업데이트 요청 알림을 발송합니다."""
    raise NotImplementedError
