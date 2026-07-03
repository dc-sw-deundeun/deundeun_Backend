from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MissionTemplate(Base):
    __tablename__ = "mission_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    verification_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    default_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class UserMission(Base):
    __tablename__ = "user_missions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "template_id",
            "assigned_date",
            name="uq_user_missions_user_template_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 엔진 생성 미션은 DB 템플릿이 없어 nullable. #24 기본미션 경로는 채운다.
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("mission_templates.id"), nullable=True, index=True
    )
    source_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("checkup_records.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ASSIGNED")
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 엔진 미션 인스턴스(하이브리드): 조회용 컬럼 + 표시용 payload.
    template_code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 변화/provenance
    payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # GeneratedMission 전체(표시용)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class MissionCompletion(Base):
    __tablename__ = "mission_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class MissionStatistics(Base):
    __tablename__ = "mission_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class MissionGenerationRun(Base):
    """미션 생성 멱등 로그 — 유저·날짜당 1행으로 스케줄러/이벤트 중복 생성을 막는다.

    UNIQUE(user_id, generation_date) + `INSERT ... ON CONFLICT DO NOTHING`로 원자적 claim한다.
    다중 인스턴스/중복 틱에도 한 유저는 하루 1회만 생성되고, status로 관측·재시도한다.
    """

    __tablename__ = "mission_generation_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "generation_date", name="uq_mission_gen_runs_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending | generated | failed | skipped
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # scheduler | event
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mission_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_now, onupdate=_now
    )
