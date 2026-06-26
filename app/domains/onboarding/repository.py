from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.onboarding.models import WearableConnection
from app.domains.user.models import User


class OnboardingRepository:
    """온보딩 도메인 영속성 계층 (SQLAlchemy)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def list_wearable_connections(self, user_id: int) -> list[WearableConnection]:
        return list(
            self.db.scalars(
                select(WearableConnection)
                .where(WearableConnection.user_id == user_id)
                .order_by(WearableConnection.provider)
            )
        )

    def find_wearable_connection(self, user_id: int, provider: str) -> WearableConnection | None:
        return self.db.scalar(
            select(WearableConnection).where(
                WearableConnection.user_id == user_id,
                WearableConnection.provider == provider,
            )
        )

    def upsert_wearable_connection(
        self,
        user_id: int,
        provider: str,
        status: str,
        scopes: list[str] | None,
    ) -> WearableConnection:
        connection = self.find_wearable_connection(user_id, provider)
        if connection is None:
            connection = WearableConnection(
                user_id=user_id,
                provider=provider,
                status=status,
                scopes=scopes,
            )
            self.db.add(connection)
        else:
            connection.status = status
            connection.scopes = scopes
        self.db.flush()
        return connection
