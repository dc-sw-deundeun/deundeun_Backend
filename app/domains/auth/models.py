import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class VerificationPurpose(str, enum.Enum):
    SIGNUP = "SIGNUP"
    PASSWORD_RESET = "PASSWORD_RESET"


class ConsentType(str, enum.Enum):
    TERMS_OF_SERVICE = "TERMS_OF_SERVICE"
    PRIVACY = "PRIVACY"
    HEALTH_DATA = "HEALTH_DATA"


class EmailVerification(Base):
    """이메일 인증 코드 관리 (회원가입·비밀번호 재설정 공용)."""

    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(
        Enum(VerificationPurpose, name="verification_purpose_enum"),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RefreshToken(Base):
    """Refresh token 회전·폐기 관리."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ConsentHistory(Base):
    """약관·민감 건강정보 동의 이력 (버전별 보존)."""

    __tablename__ = "consent_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consent_type: Mapped[str] = mapped_column(
        Enum(ConsentType, name="consent_type_enum"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    agreed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    agreed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
