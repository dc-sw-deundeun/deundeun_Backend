"""미션 완료/취소 실제 HTTP E2E — 실 회원가입·로그인·JWT로 인증 계층까지 검증.

단위 테스트(tests/domains/mission/test_mission_completion_cancel.py)는
get_current_user를 오버라이드해 서비스 로직만 검증한다. 여기서는 실제
Authorization 헤더 기반 인증, 실제 라우팅·직렬화, 그리고 캐릭터 EXP가
실 HTTP 응답에 정확히 반영되는지까지 end-to-end로 확인한다.
"""

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domains.character.models import CharacterProfile
from app.domains.mission.models import UserMission
from tests.conftest import CapturingEmailClient
from tests.test_auth_flow import login_user, signup_user

_MISSIONS = "/api/v1/missions"
_CHARACTERS = "/api/v1/characters"
_ASSIGNED_DATE = date(2026, 7, 9)


def _signup_and_login(
    client: TestClient, email_client: CapturingEmailClient, email: str
) -> tuple[str, int]:
    signup_res = signup_user(client, email_client, email=email)
    assert signup_res.status_code == 200
    user_id = signup_res.json()["data"]["user"]["id"]
    access = login_user(client, email=email).json()["data"]["access_token"]
    return access, user_id


def _seed_mission(db, user_id: int, *, xp_reward: int = 20) -> UserMission:
    row = UserMission(
        user_id=user_id,
        template_id=None,
        assigned_date=_ASSIGNED_DATE,
        status="ASSIGNED",
        xp_reward=xp_reward,
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


def _total_exp(db, user_id: int) -> int:
    db.expire_all()
    profile = db.scalar(select(CharacterProfile).where(CharacterProfile.user_id == user_id))
    return profile.total_exp if profile else 0


def test_complete_then_cancel_reverts_status_and_xp_over_http(
    client: TestClient, db_session, email_client: CapturingEmailClient
) -> None:
    access, user_id = _signup_and_login(client, email_client, "cancel-e2e-1@example.com")
    mission = _seed_mission(db_session, user_id, xp_reward=20)
    headers = {"Authorization": f"Bearer {access}"}

    complete_res = client.post(f"{_MISSIONS}/{mission.id}/complete", headers=headers)
    assert complete_res.status_code == 200

    char_res = client.get(f"{_CHARACTERS}/me", headers=headers)
    assert char_res.json()["data"]["total_exp"] == 20
    assert _total_exp(db_session, user_id) == 20

    cancel_res = client.delete(f"{_MISSIONS}/{mission.id}/complete", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["success"] is True

    char_res_after = client.get(f"{_CHARACTERS}/me", headers=headers)
    assert char_res_after.json()["data"]["total_exp"] == 0
    assert _total_exp(db_session, user_id) == 0

    db_session.expire_all()
    reverted = db_session.get(UserMission, mission.id)
    assert reverted.status == "ASSIGNED"
    assert reverted.completed_at is None


def test_repeated_complete_cancel_cycles_do_not_drift_xp(
    client: TestClient, db_session, email_client: CapturingEmailClient
) -> None:
    """오탭 반복 등으로 완료↔취소를 여러 번 반복해도 XP가 누적/파밍되지 않는다."""
    access, user_id = _signup_and_login(client, email_client, "cancel-e2e-2@example.com")
    mission = _seed_mission(db_session, user_id, xp_reward=20)
    headers = {"Authorization": f"Bearer {access}"}

    for _ in range(3):
        r1 = client.post(f"{_MISSIONS}/{mission.id}/complete", headers=headers)
        assert r1.status_code == 200
        assert _total_exp(db_session, user_id) == 20

        r2 = client.delete(f"{_MISSIONS}/{mission.id}/complete", headers=headers)
        assert r2.status_code == 200
        assert _total_exp(db_session, user_id) == 0


def test_double_complete_then_single_cancel_grants_and_revokes_once(
    client: TestClient, db_session, email_client: CapturingEmailClient
) -> None:
    """complete를 두 번(멱등) 호출해도 XP는 한 번만 지급되고, cancel도 한 번만 회수한다."""
    access, user_id = _signup_and_login(client, email_client, "cancel-e2e-3@example.com")
    mission = _seed_mission(db_session, user_id, xp_reward=20)
    headers = {"Authorization": f"Bearer {access}"}

    client.post(f"{_MISSIONS}/{mission.id}/complete", headers=headers)
    client.post(f"{_MISSIONS}/{mission.id}/complete", headers=headers)  # 멱등
    assert _total_exp(db_session, user_id) == 20

    client.delete(f"{_MISSIONS}/{mission.id}/complete", headers=headers)
    assert _total_exp(db_session, user_id) == 0

    # 이미 ASSIGNED 상태에서 재취소 — 멱등, XP 추가 회수 없음(0 미만 방지 로직에 의존하지 않음)
    cancel_again = client.delete(f"{_MISSIONS}/{mission.id}/complete", headers=headers)
    assert cancel_again.status_code == 200
    assert _total_exp(db_session, user_id) == 0


def test_cancel_other_users_mission_returns_404_and_leaves_state_untouched(
    client: TestClient, db_session, email_client: CapturingEmailClient
) -> None:
    owner_access, owner_id = _signup_and_login(client, email_client, "cancel-e2e-owner@example.com")
    _, other_id = _signup_and_login(client, email_client, "cancel-e2e-other@example.com")
    mission = _seed_mission(db_session, owner_id, xp_reward=20)

    client.post(
        f"{_MISSIONS}/{mission.id}/complete", headers={"Authorization": f"Bearer {owner_access}"}
    )
    assert _total_exp(db_session, owner_id) == 20

    other_access = login_user(client, email="cancel-e2e-other@example.com").json()["data"][
        "access_token"
    ]
    res = client.delete(
        f"{_MISSIONS}/{mission.id}/complete", headers={"Authorization": f"Bearer {other_access}"}
    )
    assert res.status_code == 404
    assert res.json()["success"] is False

    # 소유자 상태는 그대로 — 남의 취소 시도로 XP/상태가 건드려지지 않는다.
    assert _total_exp(db_session, owner_id) == 20
    assert _total_exp(db_session, other_id) == 0
    db_session.expire_all()
    untouched = db_session.get(UserMission, mission.id)
    assert untouched.status == "COMPLETED"


def test_cancel_without_auth_header_returns_401(client: TestClient, db_session) -> None:
    res = client.delete(f"{_MISSIONS}/999999/complete")
    assert res.status_code == 401
