from datetime import datetime, timedelta, timezone
from typing import Optional


def hash_password(password: str) -> str:
    """비밀번호를 해싱합니다."""
    raise NotImplementedError


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호를 검증합니다."""
    raise NotImplementedError


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """JWT Access Token을 생성합니다."""
    raise NotImplementedError


def create_refresh_token(subject: str) -> str:
    """JWT Refresh Token을 생성합니다."""
    raise NotImplementedError


def decode_token(token: str) -> dict:
    """JWT Token을 검증하고 payload를 반환합니다."""
    raise NotImplementedError


def _make_expire(expires_delta: Optional[timedelta], default_minutes: int) -> datetime:
    now = datetime.now(timezone.utc)
    return now + (expires_delta if expires_delta else timedelta(minutes=default_minutes))
