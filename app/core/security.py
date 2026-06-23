import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.domains.auth.exceptions import InvalidTokenException

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    """refresh token 등 고엔트로피 토큰을 SHA-256으로 해시한다.

    bcrypt의 72바이트 제한을 피하고, 토큰 조회 시 결정적 해시 매칭을 가능하게 한다.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    subject: str | int,
    token_version: int = 0,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "tv": token_version,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str | int) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    payload = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_verification_token(email: str, purpose: str, expires_delta: timedelta) -> str:
    """이메일 인증 완료 증명용 단기 토큰 (signup·password reset 전 단계)."""
    expire = datetime.now(UTC) + expires_delta
    payload = {
        "sub": email,
        "exp": expire,
        "type": "email_verification",
        "purpose": purpose,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """서명·만료를 검증하고 payload를 반환합니다."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise InvalidTokenException()
    return payload
