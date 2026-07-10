"""미션 완료 취소(인증 취소) — service.cancel_mission_completion + DELETE 라우터.

complete_mission과 대칭: 본인 미션 확인(404) → COMPLETED면 ASSIGNED로 되돌림(멱등).
XP 지급 연결(#71)이 아직 없어 이번 취소는 XP 롤백을 다루지 않는다.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timezone

import pytest

from app.core.exceptions import NotFoundException
from app.domains.mission.models import UserMission
from app.domains.mission.repository import MissionRepository
from app.domains.mission.service import MissionService
from app.domains.user.repository import UserRepository
from tests.domains.pkg.test_service import _create_user


def _svc(db) -> MissionService:
    return MissionService(MissionRepository(db), UserRepository(db))


def _seed_mission(db, user_id: int, status: str = "ASSIGNED") -> UserMission:
    row = UserMission(
        user_id=user_id,
        template_id=None,
        assigned_date=date(2026, 7, 9),
        status=status,
        xp_reward=20,
        template_code="walk_after_meal",
        completed_at=datetime.now(timezone.utc) if status == "COMPLETED" else None,
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


# --- service.cancel_mission_completion ---


def test_cancel_mission_completion_reverts_to_assigned(db_session) -> None:
    _create_user(db_session, 70)
    mission = _seed_mission(db_session, 70, status="COMPLETED")

    _svc(db_session).cancel_mission_completion(70, mission.id)

    reverted = MissionRepository(db_session).get_for_user(mission.id, 70)
    assert reverted is not None
    assert reverted.status == "ASSIGNED"
    assert reverted.completed_at is None


def test_cancel_mission_completion_is_idempotent_when_already_assigned(db_session) -> None:
    _create_user(db_session, 71)
    mission = _seed_mission(db_session, 71, status="ASSIGNED")

    _svc(db_session).cancel_mission_completion(71, mission.id)  # no-op, 예외 없음

    unchanged = MissionRepository(db_session).get_for_user(mission.id, 71)
    assert unchanged is not None
    assert unchanged.status == "ASSIGNED"
    assert unchanged.completed_at is None


def test_cancel_mission_completion_404_for_missing_mission(db_session) -> None:
    _create_user(db_session, 72)
    with pytest.raises(NotFoundException):
        _svc(db_session).cancel_mission_completion(72, 999999)


def test_cancel_mission_completion_404_for_other_users_mission(db_session) -> None:
    _create_user(db_session, 73)
    _create_user(db_session, 74)
    mission = _seed_mission(db_session, 73, status="COMPLETED")

    with pytest.raises(NotFoundException):
        _svc(db_session).cancel_mission_completion(74, mission.id)


# --- 라우터 통합 ---


@contextmanager
def _as_user(user_id: int) -> Iterator[None]:
    from app.core.dependencies import get_current_user
    from app.domains.user.schemas import CurrentUser
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_cancel_completion_endpoint(client, db_session) -> None:
    _create_user(db_session, 75)
    mission = _seed_mission(db_session, 75, status="COMPLETED")
    with _as_user(75):
        res = client.delete(f"/api/v1/missions/{mission.id}/complete")
        assert res.status_code == 200

    db_session.expire_all()
    reverted = MissionRepository(db_session).get_for_user(mission.id, 75)
    assert reverted is not None and reverted.status == "ASSIGNED"


def test_cancel_completion_endpoint_404_for_missing_mission(client, db_session) -> None:
    _create_user(db_session, 76)
    with _as_user(76):
        res = client.delete("/api/v1/missions/999999/complete")
        assert res.status_code == 404
