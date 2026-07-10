"""XP 지급(complete_mission) + 알림 스케줄러(run_mission_notification_tick) 단위 테스트.

XP 지급:
- ASSIGNED 미션 완료 시 CharacterProfile.total_exp가 xp_reward만큼 증가
- 두 번 호출해도 total_exp는 한 번만 증가(멱등)
- xp_reward=0이면 예외 없이 COMPLETED, total_exp 변화 없음
- gain_exp() 실패 시 미션이 ASSIGNED로 롤백되고 예외가 전파됨

알림 스케줄러:
- execution.time[:2] == 현재 로컬 시각 HH이고 ASSIGNED → Notification 1건 생성
- mission_alarm_enabled=False → Notification 미생성
- COMPLETED 미션 → 스킵
- execution.time 비어있거나 1자리 → 스킵
- 같은 조건으로 tick 두 번 → Notification 1건만 (ON CONFLICT DO NOTHING)
"""

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.domains.character.models import CharacterProfile
from app.domains.mission.models import UserMission
from app.domains.mission.repository import MissionRepository
from app.domains.mission.scheduler import run_mission_notification_tick
from app.domains.mission.service import MissionService
from app.domains.notification.models import Notification, NotificationPreference
from app.domains.user.repository import UserRepository
from tests.domains.pkg.test_service import _create_user

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

_ASSIGNED_DATE = date(2026, 7, 10)

# 서울 기준 현재 시각이 "13"이 되도록 고정하는 UTC 시각 (UTC+9 → 04:00 UTC = 13:00 KST)
_UTC_NOW_AT_KST_13 = datetime(2026, 7, 10, 4, 0, 0, tzinfo=timezone.utc)


def _svc(db) -> MissionService:
    return MissionService(MissionRepository(db), UserRepository(db))


def _seed_mission(
    db,
    user_id: int,
    *,
    xp_reward: int = 20,
    status: str = "ASSIGNED",
    exec_time: str = "13:00",
) -> UserMission:
    """테스트용 엔진 생성 미션 시드."""
    row = UserMission(
        user_id=user_id,
        template_id=None,
        assigned_date=_ASSIGNED_DATE,
        status=status,
        xp_reward=xp_reward,
        template_code="walk_after_meal",
        payload={
            "title": "식후 15분 걷기",
            "mission_type": "exercise",
            "difficulty": 2,
            "execution": {"when": "식후", "duration_min": 15, "time": exec_time},
        },
    )
    db.add(row)
    db.commit()
    return row


def _get_total_exp(db, user_id: int) -> int:
    profile = db.scalar(select(CharacterProfile).where(CharacterProfile.user_id == user_id))
    return profile.total_exp if profile else 0


# ---------------------------------------------------------------------------
# XP 지급 테스트
# ---------------------------------------------------------------------------


def test_complete_mission_grants_xp_equal_to_xp_reward(db_session) -> None:
    """ASSIGNED 미션 완료 → total_exp가 xp_reward만큼 증가한다."""
    _create_user(db_session, 1001)
    mission = _seed_mission(db_session, 1001, xp_reward=20)

    before = _get_total_exp(db_session, 1001)
    _svc(db_session).complete_mission(1001, mission.id)
    after = _get_total_exp(db_session, 1001)

    assert after - before == 20


def test_complete_mission_xp_is_idempotent_on_double_call(db_session) -> None:
    """complete_mission을 두 번 호출해도 total_exp는 한 번만 증가한다."""
    _create_user(db_session, 1002)
    mission = _seed_mission(db_session, 1002, xp_reward=20)

    before = _get_total_exp(db_session, 1002)
    svc = _svc(db_session)
    svc.complete_mission(1002, mission.id)
    svc.complete_mission(1002, mission.id)  # 멱등: no-op이어야 함
    after = _get_total_exp(db_session, 1002)

    assert after - before == 20


def test_complete_mission_with_zero_xp_reward_succeeds_without_exp_change(db_session) -> None:
    """xp_reward=0인 미션 완료 → 예외 없이 COMPLETED, total_exp 변화 없음."""
    _create_user(db_session, 1003)
    mission = _seed_mission(db_session, 1003, xp_reward=0)

    before = _get_total_exp(db_session, 1003)
    _svc(db_session).complete_mission(1003, mission.id)

    db_session.refresh(mission)
    assert mission.status == "COMPLETED"
    assert _get_total_exp(db_session, 1003) == before


def test_complete_mission_rolls_back_status_when_gain_exp_raises(db_session) -> None:
    """gain_exp()가 예외를 던지면 mission.status가 ASSIGNED로 롤백되고 예외가 전파된다."""
    _create_user(db_session, 1004)
    mission = _seed_mission(db_session, 1004, xp_reward=20)

    with patch(
        "app.domains.character.service.CharacterService.gain_exp",
        side_effect=RuntimeError("gain_exp boom"),
    ):
        with pytest.raises(RuntimeError, match="gain_exp boom"):
            _svc(db_session).complete_mission(1004, mission.id)

    # DB에서 다시 조회해 롤백 확인
    db_session.expire_all()
    refreshed = MissionRepository(db_session).get_for_user(mission.id, 1004)
    assert refreshed is not None
    assert refreshed.status == "ASSIGNED"


# ---------------------------------------------------------------------------
# 알림 스케줄러 테스트
# ---------------------------------------------------------------------------


def _seed_user_with_pkg_snapshot(db, user_id: int, timezone_name: str = "Asia/Seoul") -> None:
    """PkgRepository.list_snapshot_user_targets()가 반환하도록 pkg_snapshots 행을 시드한다.

    User.timezone이 스케줄러에서 사용되므로, _create_user가 생성하는 'Asia/Seoul' 기본값을
    활용하거나 여기서 override한다.
    """
    from app.domains.pkg.models import PkgSnapshot
    from app.domains.user.models import User

    _create_user(db, user_id)
    if timezone_name != "Asia/Seoul":
        user = db.get(User, user_id)
        user.timezone = timezone_name
        db.flush()

    snapshot = PkgSnapshot(
        user_id=user_id,
        payload={"id": str(user_id), "conditions": []},
    )
    db.add(snapshot)
    db.commit()


def test_notification_tick_creates_notification_when_hour_matches(db_session, monkeypatch) -> None:
    """execution.time[:2] == 로컬 현재 시각 HH이고 ASSIGNED → Notification 1건 생성."""
    _seed_user_with_pkg_snapshot(db_session, 2001)
    _seed_mission(db_session, 2001, exec_time="13:00")

    # local_datetime_for_timezone가 KST 13시를 반환하도록 고정
    monkeypatch.setattr(
        "app.domains.mission.scheduler.local_datetime_for_timezone",
        lambda tz, **kw: _UTC_NOW_AT_KST_13.astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Seoul")
        ),
    )

    run_mission_notification_tick()

    count = db_session.query(Notification).filter(Notification.user_id == 2001).count()
    assert count == 1
    notif = db_session.query(Notification).filter(Notification.user_id == 2001).first()
    assert notif is not None
    assert notif.type == "MISSION_REMINDER"
    assert notif.source == "mission"


def test_notification_tick_skips_user_with_alarm_disabled(db_session, monkeypatch) -> None:
    """mission_alarm_enabled=False인 유저는 Notification이 생성되지 않는다."""
    _seed_user_with_pkg_snapshot(db_session, 2002)
    db_session.add(NotificationPreference(user_id=2002, mission_alarm_enabled=False))
    db_session.commit()
    _seed_mission(db_session, 2002, exec_time="13:00")

    monkeypatch.setattr(
        "app.domains.mission.scheduler.local_datetime_for_timezone",
        lambda tz, **kw: _UTC_NOW_AT_KST_13.astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Seoul")
        ),
    )

    run_mission_notification_tick()

    count = db_session.query(Notification).filter(Notification.user_id == 2002).count()
    assert count == 0


def test_notification_tick_skips_completed_mission(db_session, monkeypatch) -> None:
    """COMPLETED 상태 미션은 알림 대상에서 제외된다."""
    _seed_user_with_pkg_snapshot(db_session, 2003)
    _seed_mission(db_session, 2003, exec_time="13:00", status="COMPLETED")

    monkeypatch.setattr(
        "app.domains.mission.scheduler.local_datetime_for_timezone",
        lambda tz, **kw: _UTC_NOW_AT_KST_13.astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Seoul")
        ),
    )

    run_mission_notification_tick()

    count = db_session.query(Notification).filter(Notification.user_id == 2003).count()
    assert count == 0


def test_notification_tick_skips_empty_execution_time(db_session, monkeypatch) -> None:
    """execution.time이 비어있으면 Notification을 생성하지 않는다."""
    _seed_user_with_pkg_snapshot(db_session, 2004)
    _seed_mission(db_session, 2004, exec_time="")

    monkeypatch.setattr(
        "app.domains.mission.scheduler.local_datetime_for_timezone",
        lambda tz, **kw: _UTC_NOW_AT_KST_13.astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Seoul")
        ),
    )

    run_mission_notification_tick()

    count = db_session.query(Notification).filter(Notification.user_id == 2004).count()
    assert count == 0


def test_notification_tick_skips_single_char_execution_time(db_session, monkeypatch) -> None:
    """execution.time이 1자리 문자열이면 IndexError 없이 스킵한다."""
    _seed_user_with_pkg_snapshot(db_session, 2005)
    _seed_mission(db_session, 2005, exec_time="1")

    monkeypatch.setattr(
        "app.domains.mission.scheduler.local_datetime_for_timezone",
        lambda tz, **kw: _UTC_NOW_AT_KST_13.astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Seoul")
        ),
    )

    run_mission_notification_tick()

    count = db_session.query(Notification).filter(Notification.user_id == 2005).count()
    assert count == 0


def test_notification_tick_is_idempotent_on_double_run(db_session, monkeypatch) -> None:
    """같은 조건으로 tick을 두 번 실행해도 Notification은 1건만 생성된다(ON CONFLICT DO NOTHING)."""
    _seed_user_with_pkg_snapshot(db_session, 2006)
    _seed_mission(db_session, 2006, exec_time="13:00")

    monkeypatch.setattr(
        "app.domains.mission.scheduler.local_datetime_for_timezone",
        lambda tz, **kw: _UTC_NOW_AT_KST_13.astimezone(
            __import__("zoneinfo").ZoneInfo("Asia/Seoul")
        ),
    )

    run_mission_notification_tick()
    run_mission_notification_tick()

    count = db_session.query(Notification).filter(Notification.user_id == 2006).count()
    assert count == 1
