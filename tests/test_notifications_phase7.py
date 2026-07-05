from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domains.character import policy
from app.domains.character.repository import CharacterRepository
from app.domains.character.service import CharacterService
from app.domains.notification.models import Notification
from app.domains.notification.repository import NotificationRepository
from app.domains.notification.service import NotificationService
from app.domains.user.models import User
from tests.conftest import CapturingEmailClient
from tests.test_auth_flow import login_user, signup_user


def _auth_headers(
    client: TestClient,
    email_client: CapturingEmailClient,
    email: str = "notification@example.com",
) -> dict[str, str]:
    signup_user(client, email_client, email=email, nickname="알림사용자")
    access = login_user(client, email=email).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {access}"}


def _user_by_email(db_session: Session, email: str) -> User:
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def _notification_count(db_session: Session, user_id: int) -> int:
    return (
        db_session.scalar(
            select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        )
        or 0
    )


def test_notifications_requires_auth(client: TestClient) -> None:
    res = client.get("/api/v1/notifications")

    assert res.status_code == 401


def test_notifications_list_read_and_home_unread_count(
    client: TestClient,
    email_client: CapturingEmailClient,
    db_session: Session,
) -> None:
    email = "notification-list@example.com"
    headers = _auth_headers(client, email_client, email)
    user = _user_by_email(db_session, email)
    NotificationService(NotificationRepository(db_session)).notify_analysis_completed(
        user_id=user.id,
        analysis_id=77,
    )

    list_res = client.get("/api/v1/notifications", headers=headers)
    home_before = client.get("/api/v1/home", headers=headers)

    assert list_res.status_code == 200
    data = list_res.json()["data"]
    assert data["total"] == 1
    assert data["unread_count"] == 1
    assert data["items"][0]["type"] == "ANALYSIS_COMPLETED"
    assert data["items"][0]["deep_link"] == "deundeun://health-metrics/analyses/77"
    assert data["items"][0]["read_at"] is None
    assert home_before.json()["data"]["unread_notification_count"] == 1

    notification_id = data["items"][0]["id"]
    read_res = client.patch(f"/api/v1/notifications/{notification_id}/read", headers=headers)
    read_again_res = client.patch(f"/api/v1/notifications/{notification_id}/read", headers=headers)
    home_after = client.get("/api/v1/home", headers=headers)

    assert read_res.status_code == 200
    assert read_res.json()["data"]["read_at"] is not None
    assert read_again_res.status_code == 200
    assert read_again_res.json()["data"]["read_at"] == read_res.json()["data"]["read_at"]
    assert home_after.json()["data"]["unread_notification_count"] == 0


def test_notifications_unread_filter_and_pagination(
    client: TestClient,
    email_client: CapturingEmailClient,
    db_session: Session,
) -> None:
    email = "notification-page@example.com"
    headers = _auth_headers(client, email_client, email)
    user = _user_by_email(db_session, email)
    service = NotificationService(NotificationRepository(db_session))
    first = service.notify_analysis_completed(user_id=user.id, analysis_id=1)
    service.notify_analysis_completed(user_id=user.id, analysis_id=2)
    service.mark_as_read(user.id, first.id)

    res = client.get(
        "/api/v1/notifications",
        params={"limit": 1, "offset": 0, "unread_only": True},
        headers=headers,
    )

    assert res.status_code == 200
    data = res.json()["data"]
    assert data["limit"] == 1
    assert data["offset"] == 0
    assert data["total"] == 1
    assert data["unread_count"] == 1
    assert [item["read_at"] for item in data["items"]] == [None]


def test_notification_read_missing_or_other_user_returns_404(
    client: TestClient,
    email_client: CapturingEmailClient,
    db_session: Session,
) -> None:
    owner_email = "notification-owner@example.com"
    other_email = "notification-other@example.com"
    _auth_headers(client, email_client, owner_email)
    other_headers = _auth_headers(client, email_client, other_email)
    owner = _user_by_email(db_session, owner_email)
    notification = NotificationService(
        NotificationRepository(db_session)
    ).notify_analysis_completed(
        user_id=owner.id,
        analysis_id=300,
    )

    res = client.patch(
        f"/api/v1/notifications/{notification.id}/read",
        headers=other_headers,
    )

    assert res.status_code == 404
    assert res.json()["error_code"] == "NOTIFICATION_NOT_FOUND"


def test_removed_notification_stub_routes_return_404(
    client: TestClient,
    email_client: CapturingEmailClient,
) -> None:
    headers = _auth_headers(client, email_client, "notification-removed@example.com")

    assert client.get("/api/v1/notifications/settings", headers=headers).status_code == 404
    assert client.patch("/api/v1/notifications/settings", headers=headers).status_code == 404
    assert client.post("/api/v1/notifications/test", headers=headers).status_code == 404


def test_notification_events_are_idempotent(db_session: Session) -> None:
    user = User(email="notification-idempotent@example.com", password_hash="hash", nickname="알림")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    service = NotificationService(NotificationRepository(db_session))

    first = service.notify_analysis_completed(user_id=user.id, analysis_id=5)
    second = service.notify_analysis_completed(user_id=user.id, analysis_id=5)

    assert first.id == second.id
    assert _notification_count(db_session, user.id) == 1


def test_health_metric_analysis_creates_notification(
    client: TestClient,
    email_client: CapturingEmailClient,
    db_session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    email = "notification-analysis@example.com"
    headers = _auth_headers(client, email_client, email)
    user = _user_by_email(db_session, email)

    res = client.post(
        "/api/v1/health-metrics/analyses",
        headers=headers,
        json={
            "sex": "male",
            "metrics": [
                {
                    "metric_code": "fasting_glucose",
                    "metric_name": "공복혈당",
                    "value": "130",
                    "unit": "mg/dL",
                }
            ],
        },
    )

    assert res.status_code == 200
    notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == "ANALYSIS_COMPLETED",
        )
    )
    assert notification is not None
    assert notification.deep_link == f"deundeun://health-metrics/analyses/{notification.source_id}"


def test_character_level_up_creates_notification(db_session: Session) -> None:
    user = User(email="notification-level@example.com", password_hash="hash", nickname="알림")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    service = CharacterService(CharacterRepository(db_session))

    service.gain_exp(
        user.id,
        policy.cumulative_exp_before_level(2),
        reason="TEST",
        source="unit",
    )

    notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.type == "LEVEL_UP",
        )
    )
    assert notification is not None
    assert notification.deep_link == "deundeun://characters/me"


def test_character_non_level_up_does_not_create_notification(db_session: Session) -> None:
    user = User(email="notification-no-level@example.com", password_hash="hash", nickname="알림")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    service = CharacterService(CharacterRepository(db_session))

    service.gain_exp(user.id, 1, reason="TEST", source="unit")

    assert _notification_count(db_session, user.id) == 0
