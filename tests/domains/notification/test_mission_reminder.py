"""NotificationService.notify_mission_reminder — 미션 리마인드 알림 생성(멱등)."""

from app.domains.notification.models import Notification
from app.domains.notification.repository import NotificationRepository
from app.domains.notification.service import MISSION_REMINDER, NotificationService
from tests.domains.pkg.test_service import _create_user


def _svc(db) -> NotificationService:
    return NotificationService(NotificationRepository(db))


def test_notify_mission_reminder_creates_notification(db_session) -> None:
    _create_user(db_session, 51)
    result = _svc(db_session).notify_mission_reminder(
        user_id=51, mission_id=100, title="식후 15분 걷기", body="13:00 예정"
    )
    assert result.type == MISSION_REMINDER
    assert result.title == "식후 15분 걷기"
    assert result.body == "13:00 예정"
    assert result.deep_link == "deundeun://missions/100"


def test_notify_mission_reminder_idempotent(db_session) -> None:
    _create_user(db_session, 52)
    svc = _svc(db_session)
    first = svc.notify_mission_reminder(user_id=52, mission_id=200, title="a", body="b")
    second = svc.notify_mission_reminder(user_id=52, mission_id=200, title="a2", body="b2")

    assert first.id == second.id  # 같은 미션 재요청 → 동일 알림(신규 생성 없음)
    count = (
        db_session.query(Notification)
        .filter(Notification.user_id == 52, Notification.source_id == "200")
        .count()
    )
    assert count == 1
