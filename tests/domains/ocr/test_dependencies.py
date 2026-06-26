from app.domains.ocr.dependencies import build_ocr_service


def test_build_ocr_service_uses_injected_session(db_session):
    service = build_ocr_service(db_session)
    assert service is not None
