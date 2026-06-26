from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OcrJob(Base):
    __tablename__ = "ocr_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True
    )  # 논리 참조, FK 없음
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # 논리 참조, FK 없음
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="CLOVA_GENERAL")
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    parsed_field_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_now, onupdate=_now
    )
