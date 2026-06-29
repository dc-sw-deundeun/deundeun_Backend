import base64

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.core.exceptions import OcrBusyException
from app.database.session import get_db
from app.domains.ocr.dependencies import get_ocr_service
from app.domains.ocr.models import OcrJob
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.ocr.status import OcrStatus
from app.domains.record.models import CheckupRecord
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
    resp = client.post("/api/v1/records/checkups/ocr-preview", json={"images": [_PNG_B64]})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["page_count"] == 1
    assert data["failed_pages"] == []
    assert data["ocr_status"] == OcrStatus.COMPLETED.value
    assert isinstance(data["metrics"], list)
    assert "record_id" not in data


def test_upload_zero_images_rejected(api):
    client, _ = api
    resp = client.post("/api/v1/records/checkups/ocr-preview", json={"images": []})
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_IMAGE_COUNT"


def test_upload_eleven_images_rejected(api):
    client, _ = api
    resp = client.post("/api/v1/records/checkups/ocr-preview", json={"images": [_PNG_B64] * 11})
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_IMAGE_COUNT"


def test_upload_invalid_base64_rejected(api):
    client, _ = api
    resp = client.post(
        "/api/v1/records/checkups/ocr-preview", json={"images": ["!!!not_base64!!!"]}
    )
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "INVALID_IMAGE_FORMAT"


def test_upload_data_uri_base64_accepted(api):
    client, _ = api
    encoded = f"data:image/png;base64,{_PNG_B64}"
    resp = client.post("/api/v1/records/checkups/ocr-preview", json={"images": [encoded]})
    assert resp.status_code == 200
    assert resp.json()["data"]["page_count"] == 1


def test_upload_multiline_base64_accepted(api):
    client, _ = api
    chunks = [_PNG_B64[i : i + 8] for i in range(0, len(_PNG_B64), 8)]
    encoded = "\n".join(chunks)
    resp = client.post("/api/v1/records/checkups/ocr-preview", json={"images": [encoded]})
    assert resp.status_code == 200


def test_upload_unsupported_format_rejected(api):
    client, _ = api
    bmp_bytes = b"BM" + b"\x00" * 30
    resp = client.post(
        "/api/v1/records/checkups/ocr-preview",
        json={"images": [base64.b64encode(bmp_bytes).decode()]},
    )
    assert resp.status_code == 415
    assert resp.json()["error_code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_single_image_too_large_rejected(api):
    client, _ = api
    raw = b"\x89PNG\r\n\x1a\n" + b"\x00" * (10 * 1024 * 1024 + 1)
    resp = client.post(
        "/api/v1/records/checkups/ocr-preview",
        json={"images": [base64.b64encode(raw).decode()]},
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "PAYLOAD_TOO_LARGE"


def test_upload_total_size_too_large_rejected(api, monkeypatch):
    client, _ = api
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_total_upload_size_bytes", len(_PNG_BYTES) + 1)
    resp = client.post(
        "/api/v1/records/checkups/ocr-preview",
        json={"images": [_PNG_B64, _PNG_B64]},
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "PAYLOAD_TOO_LARGE"


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
        "/api/v1/records/checkups/ocr-preview",
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

    resp = client.post("/api/v1/records/checkups/ocr-preview", json={"images": [_PNG_B64]})
    assert resp.status_code == 502
    assert resp.json()["error_code"] == "OCR_FAILED"


def test_upload_returns_429_when_ocr_capacity_is_busy(api):
    client, _ = api

    class _BusyOcrService:
        async def process_upload(self, user_id, images, *, content_hash=""):
            raise OcrBusyException(retry_after_seconds=10)

        def get_job(self, job_id):
            return None

    app.dependency_overrides[get_ocr_service] = lambda: _BusyOcrService()

    resp = client.post("/api/v1/records/checkups/ocr-preview", json={"images": [_PNG_B64]})
    assert resp.status_code == 429
    assert resp.headers["retry-after"] == "10"
    assert resp.json()["error_code"] == "OCR_BUSY"
    assert resp.json()["data"]["retry_after_seconds"] == 10


def test_ocr_preview_does_not_persist_db_rows(api):
    client, db = api
    resp = client.post("/api/v1/records/checkups/ocr-preview", json={"images": [_PNG_B64]})

    assert resp.status_code == 200
    assert resp.json()["data"]["page_count"] == 1
    assert db.query(CheckupRecord).all() == []
    assert db.query(OcrJob).all() == []


def test_commit_checkup_persists_record_metrics_and_audit_job(api):
    client, db = api
    content_hash = "c" * 64

    resp = client.post(
        "/api/v1/records/checkups",
        json={
            "ocr_status": "PARTIAL",
            "failed_pages": [1],
            "content_hash": content_hash,
            "metrics": [
                {
                    "metric_code": "fasting_glucose",
                    "metric_name": "공복혈당",
                    "value": "105",
                    "unit": "mg/dL",
                    "confidence": 0.91,
                    "raw_text": "109",
                    "page_index": 0,
                    "is_edited": True,
                }
            ],
        },
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["record_id"] is not None
    assert data["verification_status"] == "UNVERIFIED"
    assert len(data["metrics"]) == 1

    record = db.get(CheckupRecord, data["record_id"])
    assert record is not None
    assert record.file_url is None
    assert record.file_hash == content_hash
    assert record.ocr_status == "PARTIAL"
    assert record.verification_status == "UNVERIFIED"
    metric = RecordRepository(db).list_metrics(record.id)[0]
    assert metric.value == "105"
    assert metric.is_edited is True
    job = db.query(OcrJob).filter(OcrJob.record_id == record.id).one()
    assert job.status == "PARTIAL"
    assert job.error_message == "pages [1] failed"


def test_commit_checkup_returns_422_on_invalid_ocr_status(api):
    _, db = api

    resp = TestClient(app).post(
        "/api/v1/records/checkups",
        json={
            "ocr_status": "INVALID_STATUS",
            "failed_pages": [],
            "content_hash": "d" * 64,
            "metrics": [
                {
                    "metric_code": "fasting_glucose",
                    "metric_name": "공복혈당",
                    "value": "1",
                    "unit": "",
                    "confidence": 0.9,
                    "raw_text": "1",
                    "page_index": 0,
                }
            ],
        },
    )

    assert resp.status_code == 422
    assert db.query(CheckupRecord).all() == []
    assert db.query(OcrJob).all() == []


def test_commit_checkup_returns_422_on_metric_name_too_long(api):
    _, db = api

    resp = TestClient(app).post(
        "/api/v1/records/checkups",
        json={
            "ocr_status": "COMPLETED",
            "failed_pages": [],
            "content_hash": "e" * 64,
            "metrics": [
                {
                    "metric_code": "fasting_glucose",
                    "metric_name": "x" * 101,  # exceeds max_length=100 in schema
                    "value": "1",
                    "unit": "",
                    "confidence": 0.9,
                    "raw_text": "1",
                    "page_index": 0,
                }
            ],
        },
    )

    assert resp.status_code == 422
    assert db.query(CheckupRecord).all() == []
    assert db.query(OcrJob).all() == []
