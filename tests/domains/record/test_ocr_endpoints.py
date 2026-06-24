import io

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.domains.ocr.dependencies import (
    build_ocr_service,
    get_ocr_job_runner,
    get_ocr_service,
    get_record_service,
)
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.ocr.status import OcrStatus
from app.domains.record.repository import RecordRepository
from app.domains.record.service import RecordService
from app.domains.user.schemas import CurrentUser
from app.infrastructure.ocr.ocr_client import StubOcrClient
from app.infrastructure.ocr.parser import OcrParser, ParsedMetric
from app.infrastructure.storage.file_storage import StubFileStorage
from app.main import app

_PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"0" * 32


class MemoryStorage:
    async def upload(self, file_path, content):
        return f"s3://{file_path}"

    async def delete(self, file_path):
        return None


@pytest.fixture
def api(db_session):
    def _db():
        yield db_session

    def _user():
        return CurrentUser(id=1)

    record_service = RecordService(RecordRepository(db_session), MemoryStorage())
    ocr_service = OcrService(
        ocr_repo=OcrRepository(db_session),
        record_repo=RecordRepository(db_session),
        ocr_client=StubOcrClient(),
        file_storage=StubFileStorage(),
        parser=OcrParser(),
    )

    async def _runner(job_id: int):
        await build_ocr_service(db_session).process_single(job_id)

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_record_service] = lambda: record_service
    app.dependency_overrides[get_ocr_service] = lambda: ocr_service
    app.dependency_overrides[get_ocr_job_runner] = lambda: _runner
    yield TestClient(app), db_session
    app.dependency_overrides.clear()


def _seed_record_with_metric(db):
    repo = RecordRepository(db)
    record = repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    repo.set_ocr_status(record, OcrStatus.COMPLETED.value)
    db.commit()
    repo.upsert_ocr_metrics(
        record.id,
        [
            ParsedMetric(
                metric_code="bmi",
                metric_name="체질량지수",
                value="24.1",
                unit="kg/m2",
                confidence=0.5,
                raw_text="24.1",
            ),
        ],
    )
    db.commit()
    return record, repo.list_metrics(record.id)[0]


def test_upload_creates_record_and_job(api):
    client, db = api
    resp = client.post(
        "/api/v1/records/checkups/upload",
        files={"file": ("checkup.png", io.BytesIO(_PNG_HEADER), "image/png")},
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert "record_id" in data and "ocr_job_id" in data


def test_upload_dedup_same_hash(api):
    client, db = api
    png = _PNG_HEADER
    files = {"file": ("a.png", io.BytesIO(png), "image/png")}
    first = client.post("/api/v1/records/checkups/upload", files=files).json()["data"]
    files = {"file": ("a.png", io.BytesIO(png), "image/png")}
    second = client.post("/api/v1/records/checkups/upload", files=files).json()["data"]
    assert first["record_id"] == second["record_id"]


def test_upload_rejects_oversized_file(api, monkeypatch):
    from app.core.config import settings

    client, db = api
    monkeypatch.setattr(settings, "max_upload_size_bytes", 4)
    resp = client.post(
        "/api/v1/records/checkups/upload",
        files={"file": ("a.png", io.BytesIO(_PNG_HEADER), "image/png")},
    )
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "PAYLOAD_TOO_LARGE"


def test_upload_rejects_unsupported_format(api):
    client, db = api
    resp = client.post(
        "/api/v1/records/checkups/upload",
        files={"file": ("a.gif", io.BytesIO(b"GIF89a..."), "image/gif")},
    )
    assert resp.status_code == 415


def test_upload_png_triggers_background_ocr(api):
    client, db = api
    png = _PNG_HEADER
    resp = client.post(
        "/api/v1/records/checkups/upload",
        files={"file": ("a.png", io.BytesIO(png), "image/png")},
    )
    assert resp.status_code == 202
    # 백그라운드 러너(override)가 동기 실행되어 잡 상태가 진전됨
    from app.domains.ocr.repository import OcrRepository

    job = OcrRepository(db).get_job(resp.json()["data"]["ocr_job_id"])
    assert job.status in ("COMPLETED", "FAILED", "PROCESSING")


def test_get_metrics_returns_flags(api):
    client, db = api
    record, _ = _seed_record_with_metric(db)
    resp = client.get(f"/api/v1/records/checkups/{record.id}/metrics")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert items[0]["low_confidence"] is True


def test_patch_metric(api):
    client, db = api
    record, metric = _seed_record_with_metric(db)
    resp = client.patch(
        f"/api/v1/records/checkups/{record.id}/metrics/{metric.id}",
        json={"value": "25.0", "unit": "kg/m2"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["source"] == "MANUAL"


def test_verify_with_edits(api):
    client, db = api
    record, metric = _seed_record_with_metric(db)
    resp = client.post(
        f"/api/v1/records/checkups/{record.id}/verify",
        json={"metrics": [{"metric_id": metric.id, "value": "26.0"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["verification_status"] == "VERIFIED"
