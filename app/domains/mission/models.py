from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, UniqueConstraint
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
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ASSIGNED")
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class MissionCompletion(Base):
    __tablename__ = "mission_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class MissionStatistics(Base):
    __tablename__ = "mission_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
