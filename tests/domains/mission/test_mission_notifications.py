"""미션 알림(리마인드) 발송 — repository.get_for_user_with_template + service.send_mission_notification.

- get_for_user_with_template: 단일 미션(+템플릿 조인, 없으면 None) 조회, 타인 미션은 None.
- send_mission_notification: 본인 미션 확인(404) → mission_alarm_enabled 스킵 → 알림 생성(멱등).
"""

from datetime import date

from app.domains.mission.models import UserMission
from app.domains.mission.repository import MissionRepository
from app.domains.mission.service import MissionService
from app.domains.notification.models import Notification, NotificationPreference
from app.domains.user.repository import UserRepository
from tests.domains.pkg.test_service import _create_user


def _svc(db) -> MissionService:
    return MissionService(MissionRepository(db), UserRepository(db))


def _seed_engine_mission(db, user_id: int, mission_id_hint: int | None = None) -> UserMission:
    row = UserMission(
        user_id=user_id,
        template_id=None,
        assigned_date=date(2026, 7, 9),
        status="ASSIGNED",
        xp_reward=20,
        template_code="walk_after_meal",
        payload={
            "title": "식후 15분 걷기",
            "mission_type": "exercise",
            "difficulty": 2,
            "execution": {"when": "식후", "duration_min": 15, "time": "13:00"},
        },
    )
    db.add(row)
    db.commit()
    return row


# --- repository.get_for_user_with_template ---


def test_get_for_user_with_template_engine_mission_has_no_template(db_session) -> None:
    _create_user(db_session, 41)
    mission = _seed_engine_mission(db_session, 41)
    found = MissionRepository(db_session).get_for_user_with_template(mission.id, 41)
    assert found is not None
    row, template = found
    assert row.id == mission.id and template is None


def test_get_for_user_with_template_returns_none_for_other_user(db_session) -> None:
    _create_user(db_session, 42)
    mission = _seed_engine_mission(db_session, 42)
    assert MissionRepository(db_session).get_for_user_with_template(mission.id, 999) is None


# --- service.send_mission_notification ---


def test_send_mission_notification_success(db_session) -> None:
    _create_user(db_session, 43)
    mission = _seed_engine_mission(db_session, 43)
    result = _svc(db_session).send_mission_notification(43, mission.id)

    assert result.sent is True
    assert result.notification_id is not None
    notif = db_session.get(Notification, result.notification_id)
    assert notif.title == "식후 15분 걷기"
    assert "13:00" in notif.body
    assert notif.deep_link == f"deundeun://missions/{mission.id}"


def test_send_mission_notification_404_for_missing_mission(db_session) -> None:
    from app.core.exceptions import NotFoundException

    _create_user(db_session, 44)
    import pytest

    with pytest.raises(NotFoundException):
        _svc(db_session).send_mission_notification(44, 999999)


def test_send_mission_notification_404_for_other_users_mission(db_session) -> None:
    from app.core.exceptions import NotFoundException

    _create_user(db_session, 45)
    _create_user(db_session, 46)
    mission = _seed_engine_mission(db_session, 45)

    import pytest

    with pytest.raises(NotFoundException):
        _svc(db_session).send_mission_notification(46, mission.id)


def test_send_mission_notification_skips_when_alarm_disabled(db_session) -> None:
    _create_user(db_session, 47)
    db_session.add(NotificationPreference(user_id=47, mission_alarm_enabled=False))
    db_session.commit()
    mission = _seed_engine_mission(db_session, 47)

    result = _svc(db_session).send_mission_notification(47, mission.id)

    assert result.sent is False
    assert result.notification_id is None
    assert result.reason
    count = db_session.query(Notification).filter(Notification.user_id == 47).count()
    assert count == 0


def test_send_mission_notification_sends_when_no_preference_row(db_session) -> None:
    # 알림설정 row가 아직 없으면 기본값(활성)으로 취급한다.
    _create_user(db_session, 48)
    mission = _seed_engine_mission(db_session, 48)
    result = _svc(db_session).send_mission_notification(48, mission.id)
    assert result.sent is True


def test_send_mission_notification_idempotent_on_repeat(db_session) -> None:
    _create_user(db_session, 49)
    mission = _seed_engine_mission(db_session, 49)
    svc = _svc(db_session)
    first = svc.send_mission_notification(49, mission.id)
    second = svc.send_mission_notification(49, mission.id)

    assert first.notification_id == second.notification_id
    count = db_session.query(Notification).filter(Notification.user_id == 49).count()
    assert count == 1


# --- 라우터 통합 ---


def _as_user(user_id: int):
    from app.core.dependencies import get_current_user
    from app.domains.user.schemas import CurrentUser
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)


def _clear_override():
    from app.core.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)


def test_send_notification_endpoint(client, db_session) -> None:
    _create_user(db_session, 50)
    mission = _seed_engine_mission(db_session, 50)
    _as_user(50)
    try:
        res = client.post("/api/v1/missions/notifications/send", json={"mission_id": mission.id})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["sent"] is True and data["notification_id"] is not None
    finally:
        _clear_override()


def test_send_notification_endpoint_404_for_missing_mission(client, db_session) -> None:
    _create_user(db_session, 53)
    _as_user(53)
    try:
        res = client.post("/api/v1/missions/notifications/send", json={"mission_id": 999999})
        assert res.status_code == 404
    finally:
        _clear_override()
