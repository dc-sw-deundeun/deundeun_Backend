from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    overall_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    overall_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    normal_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    caution_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    risk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unknown_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    explanation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    results_payload: Mapped[list | None] = mapped_column(JSON, nullable=True)
    explanation_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    details_payload: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    items: Mapped[list["HealthMetricAnalysisItem"]] = relationship(
        "HealthMetricAnalysisItem",
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="HealthMetricAnalysisItem.sort_order",
    )
    highlights: Mapped[list["HealthMetricAnalysisHighlight"]] = relationship(
        "HealthMetricAnalysisHighlight",
        back_populates="analysis",
        cascade="all, delete-orphan",
        order_by="HealthMetricAnalysisHighlight.sort_order",
    )


class HealthMetricAnalysisItem(Base):
    __tablename__ = "health_metric_analysis_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("health_metric_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    input_metric_code: Mapped[str] = mapped_column(String(50), nullable=False)
    input_metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_test_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status_label: Mapped[str] = mapped_column(String(20), nullable=False)
    matched_rule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_title: Mapped[str] = mapped_column(String(100), nullable=False)
    explanation_body: Mapped[str] = mapped_column(Text, nullable=False)
    value_text: Mapped[str] = mapped_column(String(50), nullable=False)
    badge_text: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    analysis: Mapped["HealthMetricAnalysis"] = relationship(
        "HealthMetricAnalysis", back_populates="items"
    )
    range: Mapped["HealthMetricAnalysisItemRange | None"] = relationship(
        "HealthMetricAnalysisItemRange",
        back_populates="item",
        cascade="all, delete-orphan",
        uselist=False,
    )
    range_segments: Mapped[list["HealthMetricAnalysisRangeSegment"]] = relationship(
        "HealthMetricAnalysisRangeSegment",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="HealthMetricAnalysisRangeSegment.sort_order",
    )
    recommendations: Mapped[list["HealthMetricAnalysisItemRecommendation"]] = relationship(
        "HealthMetricAnalysisItemRecommendation",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="HealthMetricAnalysisItemRecommendation.sort_order",
    )


class HealthMetricAnalysisItemRange(Base):
    __tablename__ = "health_metric_analysis_item_ranges"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("health_metric_analysis_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    range_min: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    range_max: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    marker: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    marker_percent: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    active_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active_from_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    active_to_value: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    active_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    active_marker_percent: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    item: Mapped["HealthMetricAnalysisItem"] = relationship(
        "HealthMetricAnalysisItem", back_populates="range"
    )


class HealthMetricAnalysisRangeSegment(Base):
    __tablename__ = "health_metric_analysis_range_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("health_metric_analysis_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    from_value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    to_value: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    item: Mapped["HealthMetricAnalysisItem"] = relationship(
        "HealthMetricAnalysisItem", back_populates="range_segments"
    )


class HealthMetricAnalysisItemRecommendation(Base):
    __tablename__ = "health_metric_analysis_item_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("health_metric_analysis_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(100), nullable=False, default="맞춤 추천 습관", server_default="맞춤 추천 습관"
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    item: Mapped["HealthMetricAnalysisItem"] = relationship(
        "HealthMetricAnalysisItem", back_populates="recommendations"
    )


class HealthMetricAnalysisHighlight(Base):
    __tablename__ = "health_metric_analysis_highlights"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("health_metric_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    analysis: Mapped["HealthMetricAnalysis"] = relationship(
        "HealthMetricAnalysis", back_populates="highlights"
    )
