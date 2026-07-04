from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.character.models import CharacterOwnedAnimal, CharacterProfile
from app.domains.mission.models import MissionTemplate, UserMission
from app.domains.mission.policy import local_date_for_timezone
from app.domains.user.models import OnboardingStep, User
from tests.conftest import CapturingEmailClient
from tests.test_auth_flow import login_user, signup_user


def _auth_headers(
    client: TestClient, email_client: CapturingEmailClient, email: str = "home@example.com"
) -> dict[str, str]:
    signup_user(client, email_client, email=email, nickname="홈사용자")
    access = login_user(client, email=email).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {access}"}


def _user_by_email(db_session: Session, email: str) -> User:
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def _default_template(db_session: Session) -> MissionTemplate:
    template = db_session.scalar(
        select(MissionTemplate).where(MissionTemplate.code == "DEFAULT_SELF_CHECK")
    )
    assert template is not None
    return template


def test_today_missions_requires_auth(client: TestClient) -> None:
    res = client.get("/api/v1/missions/today")

    assert res.status_code == 401


def test_today_missions_returns_today_only_with_completed_count(
    client: TestClient, email_client: CapturingEmailClient, db_session: Session
) -> None:
    email = "mission-today@example.com"
    headers = _auth_headers(client, email_client, email)
    user = _user_by_email(db_session, email)
    template = _default_template(db_session)
    today = local_date_for_timezone(user.timezone)

    db_session.add_all(
        [
            UserMission(
                user_id=user.id,
                template_id=template.id,
                assigned_date=today,
                status="COMPLETED",
                xp_reward=template.default_xp,
            ),
            UserMission(
                user_id=user.id,
                template_id=template.id,
                assigned_date=today - timedelta(days=1),
                status="ASSIGNED",
                xp_reward=template.default_xp,
            ),
        ]
    )
    db_session.commit()

    res = client.get("/api/v1/missions/today", headers=headers)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["date"] == today.isoformat()
    assert data["total"] == 1
    assert data["completed"] == 1
    assert [item["status"] for item in data["items"]] == ["COMPLETED"]
    assert data["items"][0]["template_code"] == "DEFAULT_SELF_CHECK"


def test_home_creates_character_profile_and_matches_mission_today(
    client: TestClient, email_client: CapturingEmailClient, db_session: Session
) -> None:
    email = "home-lazy@example.com"
    headers = _auth_headers(client, email_client, email)
    user = _user_by_email(db_session, email)
    template = _default_template(db_session)
    today = local_date_for_timezone(user.timezone)
    db_session.add(
        UserMission(
            user_id=user.id,
            template_id=template.id,
            assigned_date=today,
            status="ASSIGNED",
            xp_reward=template.default_xp,
        )
    )
    db_session.commit()

    home_res = client.get("/api/v1/home", headers=headers)
    missions_res = client.get("/api/v1/missions/today", headers=headers)
    character_res = client.get("/api/v1/characters/me", headers=headers)

    assert home_res.status_code == 200
    assert missions_res.status_code == 200
    assert character_res.status_code == 200
    home = home_res.json()["data"]
    assert home["user"]["nickname"] == "홈사용자"
    assert home["today_missions"] == missions_res.json()["data"]
    assert home["character"]["level"] == character_res.json()["data"]["level"]
    assert home["character"]["owned_animals"][0]["animal_code"] == "frog"
    assert home["unread_notification_count"] == 0
    assert db_session.scalar(select(CharacterProfile).where(CharacterProfile.user_id == user.id))
    assert db_session.scalar(
        select(CharacterOwnedAnimal).where(CharacterOwnedAnimal.user_id == user.id)
    )


def test_home_summary_returns_compact_aggregate(
    client: TestClient, email_client: CapturingEmailClient
) -> None:
    headers = _auth_headers(client, email_client, "home-summary@example.com")

    res = client.get("/api/v1/home/summary", headers=headers)

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["nickname"] == "홈사용자"
    assert data["level"] == 1
    assert data["total_exp"] == 0
    assert data["progress_ratio"] == 0
    assert data["owned_animal_count"] == 1
    assert data["today_mission_total"] == 0
    assert data["today_mission_completed"] == 0
    assert data["unread_notification_count"] == 0


def test_onboarding_complete_prepares_character_profile(
    client: TestClient, email_client: CapturingEmailClient, db_session: Session
) -> None:
    email = "onboarding-character@example.com"
    headers = _auth_headers(client, email_client, email)
    user = _user_by_email(db_session, email)
    user.onboarding_step = OnboardingStep.CHECKUP_VERIFIED.value
    db_session.commit()

    res = client.post("/api/v1/onboarding/complete", headers=headers)

    assert res.status_code == 200
    assert db_session.scalar(select(CharacterProfile).where(CharacterProfile.user_id == user.id))
    owned = db_session.scalar(
        select(CharacterOwnedAnimal).where(CharacterOwnedAnimal.user_id == user.id)
    )
    assert owned is not None
    assert owned.animal_code == "frog"
