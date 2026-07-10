"""미션 완료 취소(인증 취소) — service.cancel_mission_completion + DELETE 라우터.

complete_mission과 대칭: 본인 미션 확인(404) → COMPLETED면 ASSIGNED로 되돌림(멱등).
complete_mission이 XP를 지급하므로(#71) 취소도 대칭적으로 지급된 XP를 회수한다.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundException
from app.domains.character.models import CharacterProfile
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


def test_cancel_mission_completion_revokes_granted_xp(db_session) -> None:
    _create_user(db_session, 80)
    mission = _seed_mission(db_session, 80, status="ASSIGNED")
    svc = _svc(db_session)
    svc.complete_mission(80, mission.id)  # xp_reward=20 지급됨

    svc.cancel_mission_completion(80, mission.id)

    profile = db_session.scalar(select(CharacterProfile).where(CharacterProfile.user_id == 80))
    assert profile is not None
    assert profile.total_exp == 0


def test_cancel_mission_completion_with_zero_xp_reward_no_exp_change(db_session) -> None:
    _create_user(db_session, 81)
    mission = _seed_mission(db_session, 81, status="ASSIGNED")
    mission.xp_reward = 0
    db_session.commit()
    svc = _svc(db_session)
    svc.complete_mission(81, mission.id)  # xp_reward=0이라 지급 없음

    svc.cancel_mission_completion(81, mission.id)

    profile = db_session.scalar(select(CharacterProfile).where(CharacterProfile.user_id == 81))
    assert profile is None or profile.total_exp == 0
    reverted = MissionRepository(db_session).get_for_user(mission.id, 81)
    assert reverted is not None and reverted.status == "ASSIGNED"


def test_cancel_mission_completion_skips_revoke_for_mission_never_actually_granted_xp(
    db_session,
) -> None:
    """레거시 데이터 등으로 gain_exp 없이 COMPLETED로 저장된 미션은 취소해도 XP를 건드리지 않는다.

    complete_mission을 거치지 않고 status="COMPLETED"만 직접 저장된 미션(예: #72 배포 전
    레코드)을 취소할 때, xp_reward만큼 무조건 revoke하면 그 사용자가 다른 미션에서 실제로
    획득한 XP까지 깎아먹는다. growth log 감사기록으로 실제 지급 여부를 확인해 회수 여부를
    결정해야 한다.
    """
    from app.domains.character.models import CharacterProfile
    from app.domains.character.repository import CharacterRepository
    from app.domains.character.service import CharacterService

    _create_user(db_session, 90)
    CharacterService(CharacterRepository(db_session)).gain_exp(
        90, 15, reason="OTHER", source="unit"
    )
    phantom = _seed_mission(db_session, 90, status="COMPLETED")  # gain_exp 없이 바로 COMPLETED

    _svc(db_session).cancel_mission_completion(90, phantom.id)

    profile = db_session.scalar(select(CharacterProfile).where(CharacterProfile.user_id == 90))
    assert profile is not None
    assert profile.total_exp == 15  # 실제로 번 XP가 건드려지지 않아야 함


def test_cancel_mission_completion_rolls_back_status_when_revoke_exp_raises(db_session) -> None:
    _create_user(db_session, 82)
    mission = _seed_mission(db_session, 82, status="ASSIGNED")
    svc = _svc(db_session)
    svc.complete_mission(82, mission.id)

    with patch(
        "app.domains.character.service.CharacterService.revoke_exp",
        side_effect=RuntimeError("revoke_exp boom"),
    ):
        with pytest.raises(RuntimeError, match="revoke_exp boom"):
            svc.cancel_mission_completion(82, mission.id)

    db_session.expire_all()
    refreshed = MissionRepository(db_session).get_for_user(mission.id, 82)
    assert refreshed is not None
    assert refreshed.status == "COMPLETED"


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
