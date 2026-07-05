from datetime import datetime

from pydantic import BaseModel


class NotificationItemResponse(BaseModel):
    id: int
    type: str
    title: str
    body: str
    deep_link: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationItemResponse]
    total: int
    unread_count: int
    limit: int
    offset: int
