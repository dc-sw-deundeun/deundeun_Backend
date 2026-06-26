from datetime import datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.auth.models import (
    AccessTokenBlacklist,
    ConsentHistory,
    EmailVerification,
    RefreshToken,
    VerificationPurpose,
)
from app.domains.user.models import User


class AuthRepository:
    """인증 도메인 영속성 계층 (SQLAlchemy)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- User ---
    def find_user_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def save_user(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def increment_failed_login(self, user: User) -> None:
        user.failed_login_count += 1

    def reset_failed_login(self, user: User) -> None:
        user.failed_login_count = 0
        user.locked_until = None

    def set_locked_until(self, user: User, locked_until: datetime) -> None:
        user.locked_until = locked_until

    def increment_token_version(self, user: User) -> None:
        user.token_version += 1

    # --- ConsentHistory ---
    def add_consent_history(
        self, user_id: int, consent_type: str, version: str, agreed: bool
    ) -> ConsentHistory:
        history = ConsentHistory(
            user_id=user_id,
            consent_type=consent_type,
            version=version,
            agreed=agreed,
        )
        self.db.add(history)
        self.db.flush()
        return history

    # --- EmailVerification ---
    def create_email_verification(self, verification: EmailVerification) -> EmailVerification:
        self.db.add(verification)
        self.db.flush()
        return verification

    def find_latest_verification(
        self, email: str, purpose: VerificationPurpose
    ) -> EmailVerification | None:
        return self.db.scalar(
            select(EmailVerification)
            .where(
                EmailVerification.email == email,
                EmailVerification.purpose == purpose,
            )
            .order_by(EmailVerification.created_at.desc())
        )

    def find_latest_unverified_verification(
        self, email: str, purpose: VerificationPurpose
    ) -> EmailVerification | None:
        return self.db.scalar(
            select(EmailVerification)
            .where(
                EmailVerification.email == email,
                EmailVerification.purpose == purpose,
                EmailVerification.verified_at.is_(None),
            )
            .order_by(EmailVerification.created_at.desc())
        )

    def find_verified_verification(
        self, email: str, purpose: VerificationPurpose
    ) -> EmailVerification | None:
        return self.db.scalar(
            select(EmailVerification)
            .where(
                EmailVerification.email == email,
                EmailVerification.purpose == purpose,
                EmailVerification.verified_at.is_not(None),
            )
            .order_by(EmailVerification.verified_at.desc())
        )

    # --- RefreshToken ---
    def save_refresh_token(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.flush()
        return token

    def find_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    def revoke_refresh_token(self, token: RefreshToken, revoked_at: datetime) -> None:
        token.revoked_at = revoked_at

    def revoke_all_user_refresh_tokens(self, user_id: int, revoked_at: datetime) -> None:
        tokens = self.db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for token in tokens:
            token.revoked_at = revoked_at

    # --- AccessTokenBlacklist ---
    def blacklist_access_token(self, jti: str, expires_at: datetime) -> None:
        """jti를 멱등하게 블랙리스트에 추가한다 (동시 로그아웃 경합 안전)."""
        if self.is_access_token_blacklisted(jti):
            return
        try:
            with self.db.begin_nested():
                self.db.add(AccessTokenBlacklist(jti=jti, expires_at=expires_at))
                self.db.flush()
        except IntegrityError:
            # 동시 요청이 먼저 삽입한 경우 — 멱등 처리
            pass

    def is_access_token_blacklisted(self, jti: str) -> bool:
        return self.db.get(AccessTokenBlacklist, jti) is not None

    def delete_expired_access_tokens(self, now: datetime) -> int:
        """만료된 블랙리스트 행을 정리한다 (주기 배치에서 호출)."""
        result = self.db.execute(
            delete(AccessTokenBlacklist).where(AccessTokenBlacklist.expires_at < now)
        )
        cursor_result = cast(CursorResult[Any], result)
        return cursor_result.rowcount or 0
