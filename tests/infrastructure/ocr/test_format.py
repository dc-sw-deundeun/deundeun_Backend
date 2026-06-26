from app.infrastructure.ocr.format import detect_image_format


def test_detects_png():
    assert detect_image_format(b"\x89PNG\r\n\x1a\n rest") == "png"


def test_detects_jpeg():
    assert detect_image_format(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "jpg"


def test_rejects_unknown():
    assert detect_image_format(b"GIF89a") is None


def test_rejects_empty():
    assert detect_image_format(b"") is None
