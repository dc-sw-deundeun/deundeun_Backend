import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.domains.auth.models import ConsentHistory, RefreshToken


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class UserSex(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"


class OnboardingStep(str, enum.Enum):
    CONSENT = "CONSENT"
    WEARABLE = "WEARABLE"
    INITIAL_CHECKUP = "INITIAL_CHECKUP"
    CHECKUP_VERIFIED = "CHECKUP_VERIFIED"
    COMPLETED = "COMPLETED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    sex: Mapped[str] = mapped_column(
        Enum(UserSex, name="user_sex_enum"),
        default=UserSex.MALE,
        server_default=UserSex.MALE.value,
        nullable=False,
    )
    onboarding_step: Mapped[str] = mapped_column(
        Enum(OnboardingStep, name="onboarding_step_enum"),
        default=OnboardingStep.CONSENT,
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Seoul", nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(UserStatus, name="user_status_enum"),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    consent_histories: Mapped[list["ConsentHistory"]] = relationship(
        "ConsentHistory", back_populates="user", cascade="all, delete-orphan"
    )
