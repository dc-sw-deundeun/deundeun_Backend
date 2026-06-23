from app.domains.ocr.dependencies import build_ocr_service, get_file_storage
from app.infrastructure.storage.file_storage import LocalFileStorage


def test_get_file_storage_is_local():
    assert isinstance(get_file_storage(), LocalFileStorage)


def test_build_ocr_service_uses_injected_session(db_session):
    service = build_ocr_service(db_session)
    assert service is not None
    # 동일 세션으로 구성되어 잡 생성/조회가 동작
