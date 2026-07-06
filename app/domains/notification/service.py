import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.domains.notification.models import Notification
from app.domains.notification.repository import NotificationRepository
from app.domains.notification.schemas import NotificationItemResponse, NotificationListResponse

ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
LEVEL_UP = "LEVEL_UP"


def run_notification_safely(
    db: Session,
    action: Callable[[], object],
    logger: logging.Logger,
    message: str,
    *log_args: object,
) -> None:
    try:
        with db.begin_nested():
            action()
        db.commit()
    except Exception:
        logger.warning(message, *log_args, exc_info=True)


class NotificationService:
    def __init__(self, repo: NotificationRepository) -> None:
        self._repo = repo

    def list_notifications(
        self,
        user_id: int,
        *,
        limit: int,
        offset: int,
        unread_only: bool,
    ) -> NotificationListResponse:
        items = self._repo.list_notifications(
            user_id,
            limit=limit,
            offset=offset,
            unread_only=unread_only,
        )
        return NotificationListResponse(
            items=[self._to_item(row) for row in items],
            total=self._repo.count_notifications(user_id, unread_only=unread_only),
            unread_count=self._repo.count_unread(user_id),
            limit=limit,
            offset=offset,
        )

    def mark_as_read(self, user_id: int, notification_id: int) -> NotificationItemResponse:
        notification = self._repo.get_for_user(notification_id, user_id)
        if notification is None:
            raise NotFoundException(
                message="알림을 찾을 수 없습니다.",
                error_code="NOTIFICATION_NOT_FOUND",
            )
        self._repo.mark_read(notification, datetime.now(UTC))
        self._repo.commit()
        return self._to_item(notification)

    def count_unread(self, user_id: int) -> int:
        return self._repo.count_unread(user_id)

    def notify_analysis_completed(
        self, *, user_id: int, analysis_id: int, commit: bool = True
    ) -> NotificationItemResponse:
        return self._create_and_return(
            user_id=user_id,
            notification_type=ANALYSIS_COMPLETED,
            title="건강 분석이 완료됐어요",
            body="건강 지표 분석 결과를 확인해 보세요.",
            deep_link=f"deundeun://health-metrics/analyses/{analysis_id}",
            source="health_metric",
            source_id=str(analysis_id),
            commit=commit,
        )

    def notify_level_up(
        self,
        *,
        user_id: int,
        growth_log_id: int,
        after_level: int,
        commit: bool = True,
    ) -> NotificationItemResponse:
        return self._create_and_return(
            user_id=user_id,
            notification_type=LEVEL_UP,
            title="캐릭터가 레벨업했어요",
            body=f"Lv.{after_level} 달성! 새로 열린 동물을 확인해 보세요.",
            deep_link="deundeun://characters/me",
            source="character",
            source_id=f"growth_log:{growth_log_id}",
            commit=commit,
        )

    def _create_and_return(
        self,
        *,
        user_id: int,
        notification_type: str,
        title: str,
        body: str,
        deep_link: str | None,
        source: str,
        source_id: str,
        commit: bool,
    ) -> NotificationItemResponse:
        notification = self._repo.create_if_not_exists(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            deep_link=deep_link,
            source=source,
            source_id=source_id,
        )
        if commit:
            self._repo.commit()
        return self._to_item(notification)

    @staticmethod
    def _to_item(notification: Notification) -> NotificationItemResponse:
        return NotificationItemResponse(
            id=notification.id,
            type=notification.type,
            title=notification.title,
            body=notification.body,
            deep_link=notification.deep_link,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )
