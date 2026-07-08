from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.auth.models import RefreshToken
from app.domains.user.models import User


class UserRepository:
    """사용자 도메인 영속성 계층 (SQLAlchemy)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def find_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def exists_by_email(self, email: str) -> bool:
        return self.db.scalar(select(User.id).where(User.email == email)) is not None

    def commit(self) -> None:
        self.db.commit()

    def revoke_all_refresh_tokens(self, user_id: int, revoked_at: datetime) -> None:
        tokens = self.db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for token in tokens:
            token.revoked_at = revoked_at
