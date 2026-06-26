from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import AuthException
from app.core.security import decode_token
from app.database.session import get_db, session_scope
from app.domains.auth.repository import AuthRepository
from app.domains.auth.service import AuthService
from app.domains.onboarding.repository import OnboardingRepository
from app.domains.onboarding.service import OnboardingService
from app.domains.user.models import User, UserStatus
from app.domains.user.repository import UserRepository
from app.domains.user.schemas import CurrentUser
from app.infrastructure.email.email_client import EmailClient
from app.infrastructure.email.factory import get_email_client
from app.infrastructure.wearable.factory import get_wearable_client
from app.infrastructure.wearable.wearable_client import WearableClient

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


def get_wearable_client_dep() -> WearableClient:
    return get_wearable_client()


def get_onboarding_service(
    db: Session = Depends(get_db),
    wearable_client: WearableClient = Depends(get_wearable_client_dep),
) -> OnboardingService:
    return OnboardingService(OnboardingRepository(db), wearable_client)


def _authenticate(credentials: HTTPAuthorizationCredentials | None, db: Session) -> User:
    """Bearer access token을 검증하고 활성 사용자 엔티티를 반환합니다."""
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

    jti = payload.get("jti")
    if not jti:
        raise AuthException(message="유효하지 않은 토큰입니다.", error_code="INVALID_TOKEN")

    repo = AuthRepository(db)
    if repo.is_access_token_blacklisted(jti):
        raise AuthException(message="만료된 토큰입니다.", error_code="INVALID_TOKEN")

    user = repo.get_user_by_id(user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise AuthException(message="유효하지 않은 토큰입니다.", error_code="INVALID_TOKEN")

    if payload.get("tv") != user.token_version:
        raise AuthException(message="만료된 토큰입니다.", error_code="INVALID_TOKEN")

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Bearer access token을 검증하고 CurrentUser를 반환합니다."""
    if credentials is None:
        raise AuthException()

    with session_scope() as db:
        return CurrentUser(id=_authenticate(credentials, db).id)


def get_current_user_model(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    """Bearer access token을 검증하고 사용자 ORM 엔티티를 반환합니다."""
    if credentials is None:
        raise AuthException()

    with session_scope() as db:
        return _authenticate(credentials, db)
