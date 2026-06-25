from app.domains.ocr.status import MetricSource, OcrStatus, VerificationStatus


def test_ocr_status_values():
    assert OcrStatus.PENDING == "PENDING"
    assert {s.value for s in OcrStatus} == {
        "PENDING",
        "PROCESSING",
        "COMPLETED",
        "PARTIAL",
        "FAILED",
    }


def test_verification_status_values():
    assert {s.value for s in VerificationStatus} == {"UNVERIFIED", "VERIFIED"}


def test_metric_source_values():
    assert {s.value for s in MetricSource} == {"OCR", "MANUAL"}
