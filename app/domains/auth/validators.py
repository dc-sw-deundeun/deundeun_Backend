"""인증 도메인 공용 검증 로직."""

import re

from app.domains.auth.exceptions import WeakPasswordException

# 8자 이상, 영문·숫자·특수문자 각각 1개 이상 (FR-AUTH-004)
_PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")


def validate_password_policy(password: str) -> str:
    """비밀번호 정책을 검증하고 통과 시 원본을 반환한다.

    정책 위반 시 ``WeakPasswordException``을 던진다.
    """
    if not _PASSWORD_PATTERN.match(password):
        raise WeakPasswordException()
    return password
