from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthException
from app.core.security import decode_token
from app.database.session import get_db
from app.domains.auth.repository import AuthRepository
from app.domains.auth.service import AuthService
from app.domains.user.models import UserStatus
from app.domains.user.repository import UserRepository
from app.domains.user.schemas import CurrentUser
from app.infrastructure.email.email_client import EmailClient
from app.infrastructure.email.factory import get_email_client

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="JWT access token (로그인 응답의 access_token)",
)


def get_email_client_dep() -> EmailClient:
    return get_email_client()


def get_auth_service(
    db: Session = Depends(get_db),
    email_client: EmailClient = Depends(get_email_client_dep),
) -> AuthService:
    return AuthService(AuthRepository(db), email_client)


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Bearer access token을 검증하고 CurrentUser를 반환합니다."""
    if credentials is None:
        raise AuthException()

    payload = decode_token(credentials.credentials)

    if payload.get("type") != "access":
        raise AuthException(message="유효하지 않은 토큰입니다.", error_code="INVALID_TOKEN")

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise AuthException(message="토큰에 사용자 정보가 없습니다.", error_code="INVALID_TOKEN")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise AuthException(message="토큰에 사용자 정보가 없습니다.", error_code="INVALID_TOKEN")

    repo = AuthRepository(db)

    jti = payload.get("jti")
    if jti and repo.is_access_token_blacklisted(jti):
        raise AuthException(message="만료된 토큰입니다.", error_code="INVALID_TOKEN")

    user = repo.get_user_by_id(user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AuthException(message="유효하지 않은 토큰입니다.", error_code="INVALID_TOKEN")

    if payload.get("tv") != user.token_version:
        raise AuthException(message="만료된 토큰입니다.", error_code="INVALID_TOKEN")

    return CurrentUser(id=user_id)
