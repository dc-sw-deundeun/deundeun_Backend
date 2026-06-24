import base64

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.domains.ocr.dependencies import get_ocr_service
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.ocr.status import OcrStatus
from app.domains.record.repository import RecordRepository
from app.domains.user.schemas import CurrentUser
from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser
from app.main import app

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_PNG_B64 = base64.b64encode(_PNG_BYTES).decode()


class _StubOcrClient:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    async def recognize(self, image, image_format="png"):
        if self._error:
            raise self._error
        return self._result or OcrResultDTO(
            fields=[
                OcrFieldDTO(text="공복혈당", confidence=0.95, x_min=10, x_max=40, y_center=100),
                OcrFieldDTO(text="109", confidence=0.95, x_min=120, x_max=150, y_center=100),
            ]
        )


@pytest.fixture
def api(db_session):
    def _db():
        yield db_session

    def _user():
        return CurrentUser(id=1)

    service = OcrService(
        ocr_repo=OcrRepository(db_session),
        record_repo=RecordRepository(db_session),
        ocr_client=_StubOcrClient(),
        parser=OcrParser(),
    )
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_ocr_service] = lambda: service
    yield TestClient(app), db_session
    app.dependency_overrides.clear()


def test_upload_single_image_success(api):
    client, _ = api
    resp = client.post("/api/v1/records/checkups/upload", json={"images": [_PNG_B64]})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page_count"] == 1
    assert data["failed_pages"] == []
    assert data["ocr_status"] == OcrStatus.COMPLETED.value
    assert isinstance(data["metrics"], list)


def test_upload_zero_images_rejected(api):
    client, _ = api
    resp = client.post("/api/v1/records/checkups/upload", json={"images": []})
    assert resp.status_code == 422


def test_upload_eleven_images_rejected(api):
    client, _ = api
    resp = client.post("/api/v1/records/checkups/upload", json={"images": [_PNG_B64] * 11})
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_IMAGE_COUNT"


def test_upload_invalid_base64_rejected(api):
    client, _ = api
    resp = client.post("/api/v1/records/checkups/upload", json={"images": ["!!!not_base64!!!"]})
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_IMAGE_FORMAT"


def test_upload_unsupported_format_rejected(api):
    client, _ = api
    bmp_bytes = b"BM" + b"\x00" * 30
    resp = client.post(
        "/api/v1/records/checkups/upload",
        json={"images": [base64.b64encode(bmp_bytes).decode()]},
    )
    assert resp.status_code == 415
    assert resp.json()["error_code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_partial_failure_response(api):
    client, db = api
    call_count = 0

    class _PartialClient:
        async def recognize(self, image, image_format="png"):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("clova timeout")
            return OcrResultDTO(
                fields=[
                    OcrFieldDTO(text="공복혈당", confidence=0.9, x_min=10, x_max=40, y_center=100),
                    OcrFieldDTO(text="109", confidence=0.9, x_min=120, x_max=150, y_center=100),
                ]
            )

    service = OcrService(
        ocr_repo=OcrRepository(db),
        record_repo=RecordRepository(db),
        ocr_client=_PartialClient(),
        parser=OcrParser(),
        max_retries=0,
    )
    app.dependency_overrides[get_ocr_service] = lambda: service

    resp = client.post(
        "/api/v1/records/checkups/upload",
        json={"images": [_PNG_B64, _PNG_B64, _PNG_B64]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ocr_status"] == OcrStatus.PARTIAL.value
    assert 1 in data["failed_pages"]


def test_upload_all_fail_returns_502(api):
    client, db = api

    class _FailClient:
        async def recognize(self, image, image_format="png"):
            raise RuntimeError("all fail")

    service = OcrService(
        ocr_repo=OcrRepository(db),
        record_repo=RecordRepository(db),
        ocr_client=_FailClient(),
        parser=OcrParser(),
    )
    app.dependency_overrides[get_ocr_service] = lambda: service

    resp = client.post("/api/v1/records/checkups/upload", json={"images": [_PNG_B64]})
    assert resp.status_code == 502
    assert resp.json()["error_code"] == "OCR_FAILED"


def test_no_file_url_stored(api):
    client, db = api
    resp = client.post("/api/v1/records/checkups/upload", json={"images": [_PNG_B64]})
    record_id = resp.json()["data"]["record_id"]
    record = RecordRepository(db).get_record(record_id)
    assert record is not None
    assert record.file_url is None
    assert record.file_hash is None
