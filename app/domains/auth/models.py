import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.domains.user.models import User


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
    __table_args__ = (
        Index(
            "ix_email_verifications_email_purpose_verified_at",
            "email",
            "purpose",
            "verified_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(
        Enum(VerificationPurpose, name="verification_purpose_enum"),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RefreshToken(Base):
    """Refresh token 회전·폐기 관리."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index(
            "ix_refresh_tokens_user_id_revoked_at_expires_at",
            "user_id",
            "revoked_at",
            "expires_at",
        ),
    )

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

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class AccessTokenBlacklist(Base):
    """로그아웃된 access token의 jti 블랙리스트.

    access token은 만료가 짧지만, 로그아웃 즉시 무효화하기 위해 jti를 기록한다.
    expires_at 이후의 행은 조회 시 무시되며 주기적으로 정리할 수 있다.
    """

    __tablename__ = "access_token_blacklist"
    __table_args__ = (Index("ix_access_token_blacklist_expires_at", "expires_at"),)

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ConsentHistory(Base):
    """약관·민감 건강정보 동의 이력 (버전별 보존)."""

    __tablename__ = "consent_histories"
    __table_args__ = (
        Index(
            "ix_consent_histories_user_id_consent_type_agreed_at",
            "user_id",
            "consent_type",
            "agreed_at",
        ),
    )

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

    user: Mapped["User"] = relationship("User", back_populates="consent_histories")
