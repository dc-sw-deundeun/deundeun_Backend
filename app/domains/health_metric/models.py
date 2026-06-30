from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

import app.domains.auth.models  # noqa: F401
from app.database.base import Base
from app.domains.record.models import CheckupRecord  # noqa: F401
from app.domains.user.models import User  # noqa: F401


class HealthMetricReference(Base):
    __tablename__ = "health_metric_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)


class HealthMetricAnalysis(Base):
    __tablename__ = "health_metric_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    record_id: Mapped[int | None] = mapped_column(
        ForeignKey("checkup_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sex: Mapped[str | None] = mapped_column(String(20), nullable=True)
    measured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    results_payload: Mapped[list] = mapped_column(JSON, nullable=False)
    explanation_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    summary_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    details_payload: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
