import base64
import re

_DATA_URI_PREFIX = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,", re.IGNORECASE)


def normalize_base64_image(encoded: str) -> str:
    """업로드용 base64 문자열을 정규화한다.

    data URI 접두사와 공백·줄바꿈을 제거해 클라이언트 포맷 차이를 흡수한다.
    """
    value = encoded.strip()
    value = _DATA_URI_PREFIX.sub("", value)
    return "".join(value.split())


def decode_base64_image(encoded: str) -> bytes:
    """정규화된 base64 이미지 payload를 bytes로 디코드한다."""
    normalized = normalize_base64_image(encoded)
    if not normalized:
        raise ValueError("empty image payload")

    try:
        return base64.b64decode(normalized, validate=True)
    except Exception:
        padded = normalized + "=" * (-len(normalized) % 4)
        try:
            return base64.b64decode(padded, validate=True)
        except Exception as second_exc:
            raise ValueError("invalid base64 encoding") from second_exc
