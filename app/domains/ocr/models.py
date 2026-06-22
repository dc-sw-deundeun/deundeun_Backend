from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OcrJob(Base):
    __tablename__ = "ocr_jobs"

    id = Column(Integer, primary_key=True)
    record_id = Column(Integer, nullable=False, index=True)  # 논리 참조, FK 없음
    user_id = Column(Integer, nullable=False, index=True)    # 논리 참조, FK 없음
    provider = Column(String(50), nullable=False, default="CLOVA_GENERAL")
    status = Column(String(20), nullable=False)
    raw_result_url = Column(String(500), nullable=True)
    parsed_field_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    requested_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
