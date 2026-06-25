from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

import app.domains.auth.models  # noqa: F401
from app.database.base import Base
from app.domains.user.models import User  # noqa: F401


class HealthMetricReference(Base):
    __tablename__ = "health_metric_references"

    id = Column(Integer, primary_key=True)
    # metric_code, metric_name, description, reference_min, reference_max, unit
    # recommendations, avoidances


class HealthMetricAnalysis(Base):
    __tablename__ = "health_metric_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
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
