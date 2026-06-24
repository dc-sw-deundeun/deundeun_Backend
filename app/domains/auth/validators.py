"""인증 도메인 공용 검증 로직."""

import re

from app.domains.auth.exceptions import WeakPasswordException

# 8자 이상, 영문·숫자·특수문자 각각 1개 이상 (FR-AUTH-004)
_PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")

# bcrypt는 72바이트 초과분을 잘라내므로, 그 이전에 거부해 해시 충돌을 방지한다.
_PASSWORD_MAX_BYTES = 72


def validate_password_policy(password: str) -> str:
    """비밀번호 정책을 검증하고 통과 시 원본을 반환한다.

    정책 위반 시 ``WeakPasswordException``을 던진다.
    """
    if len(password.encode("utf-8")) > _PASSWORD_MAX_BYTES:
        raise WeakPasswordException()
    if not _PASSWORD_PATTERN.match(password):
        raise WeakPasswordException()
    return password
