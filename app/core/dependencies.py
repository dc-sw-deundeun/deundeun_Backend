from collections.abc import Generator

from fastapi import Depends


def get_db() -> Generator:
    """DB 세션을 반환합니다. DB 확정 후 구현합니다."""
    raise NotImplementedError


def get_current_user(token: str = Depends(lambda: None)):
    """현재 로그인한 사용자를 반환합니다. Auth 구현 후 활성화합니다."""
    raise NotImplementedError


def get_current_admin(current_user=Depends(get_current_user)):
    """관리자 권한을 확인합니다."""
    raise NotImplementedError
