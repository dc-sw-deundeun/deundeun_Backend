from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.database.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CheckupRecord(Base):
    __tablename__ = "checkup_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)  # 논리 참조, FK 없음
    source_type = Column(String(20), nullable=False)
    file_url = Column(String(500), nullable=True)
    file_hash = Column(String(64), nullable=True, index=True)
    measured_at = Column(DateTime, nullable=True)
    ocr_status = Column(String(20), nullable=True)
    verification_status = Column(String(20), nullable=False, default="UNVERIFIED")
    verified_at = Column(DateTime, nullable=True)
    analysis_status = Column(String(20), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class CheckupMetricResult(Base):
    __tablename__ = "checkup_metric_results"

    id = Column(Integer, primary_key=True)
    record_id = Column(Integer, nullable=False, index=True)  # 논리 참조, FK 없음
    metric_code = Column(String(50), nullable=False)
    metric_name = Column(String(100), nullable=False)
    value = Column(String(50), nullable=True)
    unit = Column(String(20), nullable=True)
    status = Column(String(20), nullable=True)
    reference_min = Column(Float, nullable=True)
    reference_max = Column(Float, nullable=True)
    interpretation = Column(Text, nullable=True)
    source = Column(String(20), nullable=False, default="OCR")
    confidence = Column(Float, nullable=True)
    raw_text = Column(String(200), nullable=True)
    is_edited = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)


class CheckupFile(Base):
    __tablename__ = "checkup_files"

    id = Column(Integer, primary_key=True)
    # record_id, file_url, file_type, created_at


class MealRecord(Base):
    __tablename__ = "meal_records"

    id = Column(Integer, primary_key=True)
    # user_id, image_url, recognized_result, verified_status, created_at
