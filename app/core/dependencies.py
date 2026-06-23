from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthException
from app.core.security import decode_token
from app.database.session import get_db  # noqa: F401 — re-export
from app.domains.user.schemas import CurrentUser

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    """Bearer 토큰을 검증하고 CurrentUser를 반환합니다."""
    if credentials is None:
        raise AuthException()

    payload = decode_token(credentials.credentials)
    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise AuthException(message="토큰에 사용자 정보가 없습니다.", error_code="INVALID_TOKEN")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise AuthException(message="토큰에 사용자 정보가 없습니다.", error_code="INVALID_TOKEN")

    return CurrentUser(id=user_id)
