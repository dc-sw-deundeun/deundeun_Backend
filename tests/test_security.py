"""security.py 단위 테스트 — DB 불필요."""

from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domains.auth.exceptions import InvalidTokenException


def test_hash_and_verify_password() -> None:
    hashed = hash_password("my-secret")
    assert hashed != "my-secret"
    assert verify_password("my-secret", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_encode_decode() -> None:
    token = create_access_token(subject=7)
    payload = decode_token(token)
    assert payload["sub"] == "7"
    assert payload["type"] == "access"


def test_refresh_token_encode_decode() -> None:
    token = create_refresh_token(subject=99)
    payload = decode_token(token)
    assert payload["sub"] == "99"
    assert payload["type"] == "refresh"


def test_decode_invalid_token_raises() -> None:
    with pytest.raises(InvalidTokenException):
        decode_token("garbage.token.here")


def test_decode_expired_token_raises() -> None:
    token = create_access_token(subject=1, expires_delta=timedelta(seconds=-1))
    with pytest.raises(InvalidTokenException):
        decode_token(token)
