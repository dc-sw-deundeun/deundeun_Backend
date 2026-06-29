import base64

import pytest

from app.infrastructure.ocr.encoding import decode_base64_image, normalize_base64_image

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_PNG_B64 = base64.b64encode(_PNG_BYTES).decode()


def test_normalize_base64_image_strips_data_uri_prefix() -> None:
    encoded = f"data:image/png;base64,{_PNG_B64}"
    assert normalize_base64_image(encoded) == _PNG_B64


def test_normalize_base64_image_strips_whitespace() -> None:
    chunks = [_PNG_B64[i : i + 4] for i in range(0, len(_PNG_B64), 4)]
    encoded = "\n".join(chunks)
    assert normalize_base64_image(encoded) == _PNG_B64


def test_decode_base64_image_accepts_data_uri() -> None:
    encoded = f"data:image/png;base64,{_PNG_B64}"
    assert decode_base64_image(encoded) == _PNG_BYTES


def test_decode_base64_image_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError, match="invalid base64"):
        decode_base64_image("!!!not-base64!!!")
