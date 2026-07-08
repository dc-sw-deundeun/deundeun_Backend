from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.character.models import CharacterOwnedAnimal
from app.domains.mission.models import UserMission
from app.domains.notification.models import Notification
from app.domains.record.models import CheckupRecord
from app.domains.user.models import User
from scripts import seed_demo_data


def _login_demo(client: TestClient, email: str) -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": seed_demo_data.DEMO_PASSWORD},
    )
    assert res.status_code == 200
    token = res.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _user_id(db: Session, email: str) -> int:
    user_id = db.scalar(select(User.id).where(User.email == email))
    assert user_id is not None
    return user_id


def test_seed_demo_data_is_idempotent_and_covers_frontend_flows(
    client: TestClient, db_session: Session
) -> None:
    seed_demo_data.main()
    seed_demo_data.main()
    db_session.expire_all()

    assert (
        db_session.scalar(
            select(func.count()).select_from(User).where(User.email.in_(seed_demo_data.DEMO_EMAILS))
        )
        == 3
    )

    demo_user_id = _user_id(db_session, "demo-user@demo.deundeun.xyz")
    demo_growth_id = _user_id(db_session, "demo-growth@demo.deundeun.xyz")

    assert (
        db_session.scalar(
            select(func.count())
            .select_from(CheckupRecord)
            .where(CheckupRecord.user_id == demo_user_id)
        )
        == 2
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(UserMission).where(UserMission.user_id == demo_user_id)
        )
        == 63
    )
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == demo_user_id)
        )
        == 2
    )
    owned_animal_count = db_session.scalar(
        select(func.count())
        .select_from(CharacterOwnedAnimal)
        .where(CharacterOwnedAnimal.user_id == demo_growth_id)
    )
    assert owned_animal_count is not None
    assert owned_animal_count >= 4

    headers = _login_demo(client, "demo-user@demo.deundeun.xyz")
    for path in (
        "/api/v1/home",
        "/api/v1/my/profile",
        "/api/v1/my/notification-settings",
        "/api/v1/records/checkups",
        "/api/v1/missions/today",
        "/api/v1/notifications",
        "/api/v1/characters/animals",
    ):
        res = client.get(path, headers=headers)
        assert res.status_code == 200, path

    growth_headers = _login_demo(client, "demo-growth@demo.deundeun.xyz")
    character_res = client.get("/api/v1/characters/me", headers=growth_headers)
    assert character_res.status_code == 200
    assert [a["animal_code"] for a in character_res.json()["data"]["owned_animals"]][:4] == [
        "frog",
        "chick",
        "penguin",
        "dog",
    ]

    new_headers = _login_demo(client, "demo-new@demo.deundeun.xyz")
    profile_res = client.get("/api/v1/my/profile", headers=new_headers)
    assert profile_res.status_code == 200
    assert profile_res.json()["data"]["onboarding_step"] == "CONSENT"
