from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
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
        stmt = (
            insert(WearableConnection)
            .values(
                user_id=user_id,
                provider=provider,
                status=status,
                scopes=scopes,
            )
            .on_conflict_do_update(
                constraint="uq_wearable_connections_user_provider",
                set_={
                    "status": status,
                    "scopes": scopes,
                    "updated_at": func.now(),
                },
            )
            .returning(WearableConnection.id)
        )
        connection_id = self.db.scalar(stmt)
        self.db.flush()
        connection = self.db.get(WearableConnection, connection_id, populate_existing=True)
        if connection is None:
            raise RuntimeError("Failed to upsert wearable connection")
        return connection

    def delete_wearable_connection(self, user_id: int, provider: str) -> bool:
        connection = self.find_wearable_connection(user_id, provider)
        if connection is None:
            return False
        self.db.delete(connection)
        self.db.flush()
        return True
