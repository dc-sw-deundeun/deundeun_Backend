def test_ocr_failed_exception():
    from app.core.exceptions import OcrFailedException

    exc = OcrFailedException()

    assert exc.status_code == 502
    assert exc.error_code == "OCR_FAILED"


def test_invalid_image_count_exception():
    from app.core.exceptions import InvalidImageCountException

    exc = InvalidImageCountException()

    assert exc.status_code == 400
    assert exc.error_code == "INVALID_IMAGE_COUNT"


def test_ocr_busy_exception():
    from app.core.exceptions import OcrBusyException

    exc = OcrBusyException(retry_after_seconds=10)

    assert exc.status_code == 429
    assert exc.error_code == "OCR_BUSY"
    assert exc.retry_after_seconds == 10
