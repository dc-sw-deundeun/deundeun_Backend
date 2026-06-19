"""주기적 작업 스케줄러입니다. APScheduler 또는 Celery Beat 등으로 구현합니다."""


def start_scheduler() -> None:
    """스케줄러를 시작합니다. DB 확정 후 lifespan에서 호출합니다.

    등록 예정 작업:
    - 매일 오전 9시: 오늘의 미션 알림
    - 매일 오후 8시: 미션 미완료 알림
    - 매주 일요일: 주간 통계 생성
    - 주기적: 검진 등록 주기 알림
    """
    raise NotImplementedError


def stop_scheduler() -> None:
    raise NotImplementedError
