from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domains.notification.models import Notification, NotificationPreference


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()

    def list_notifications(
        self,
        user_id: int,
        *,
        limit: int,
        offset: int,
        unread_only: bool,
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
        stmt = stmt.limit(limit).offset(offset)
        return list(self._db.scalars(stmt))

    def count_notifications(self, user_id: int, *, unread_only: bool) -> int:
        stmt = select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        return self._db.scalar(stmt) or 0

    def count_unread(self, user_id: int) -> int:
        return self.count_notifications(user_id, unread_only=True)

    def get_for_user(self, notification_id: int, user_id: int) -> Notification | None:
        return self._db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )

    def find_by_source(
        self,
        *,
        user_id: int,
        notification_type: str,
        source: str,
        source_id: str,
    ) -> Notification | None:
        return self._db.scalar(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.type == notification_type,
                Notification.source == source,
                Notification.source_id == source_id,
            )
        )

    def create_if_not_exists(
        self,
        *,
        user_id: int,
        notification_type: str,
        title: str,
        body: str,
        deep_link: str | None,
        source: str,
        source_id: str,
    ) -> Notification:
        stmt = (
            pg_insert(Notification)
            .values(
                user_id=user_id,
                type=notification_type,
                title=title,
                body=body,
                deep_link=deep_link,
                source=source,
                source_id=source_id,
            )
            .on_conflict_do_nothing(constraint="uq_notifications_user_type_source")
            .returning(Notification)
        )
        result = self._db.execute(stmt)
        row = result.scalars().first()
        if row is not None:
            return row

        existing = self.find_by_source(
            user_id=user_id,
            notification_type=notification_type,
            source=source,
            source_id=source_id,
        )
        if existing is None:
            raise RuntimeError("notification upsert failed without existing row")
        return existing

    def mark_read(self, notification: Notification, read_at: datetime) -> Notification:
        if notification.read_at is None:
            notification.read_at = read_at
            self._db.flush()
        return notification

    def find_preference_by_user_id(self, user_id: int) -> NotificationPreference | None:
        return self._db.scalar(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
