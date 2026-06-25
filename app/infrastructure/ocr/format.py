_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def detect_image_format(content: bytes) -> str | None:
    """매직넘버로 jpg/png를 판별한다. 미지원 포맷은 None."""
    if content.startswith(_PNG_MAGIC):
        return "png"
    if content.startswith(_JPEG_MAGIC):
        return "jpg"
    return None
