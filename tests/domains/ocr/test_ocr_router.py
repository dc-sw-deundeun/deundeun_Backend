import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.domains.ocr.dependencies import (
    build_ocr_service,
    get_ocr_job_runner,
    get_ocr_service,
)
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.record.repository import RecordRepository
from app.domains.user.schemas import CurrentUser
from app.infrastructure.ocr.ocr_client import StubOcrClient
from app.infrastructure.ocr.parser import OcrParser
from app.infrastructure.storage.file_storage import StubFileStorage
from app.main import app


class _FileStorageStub:
    def __init__(self, exists_value: bool) -> None:
        self._exists_value = exists_value

    async def upload(self, file_path: str, content: bytes) -> str:
        return file_path

    async def read(self, file_path: str) -> bytes:
        return b""

    async def delete(self, file_path: str) -> None:
        return None

    async def exists(self, file_path: str) -> bool:
        return self._exists_value


@pytest.fixture
def api_client(db_session):
    def _override_db():
        yield db_session

    def _override_user():
        return CurrentUser(id=1)

    service = OcrService(
        ocr_repo=OcrRepository(db_session),
        record_repo=RecordRepository(db_session),
        ocr_client=StubOcrClient(),
        file_storage=StubFileStorage(),
        parser=OcrParser(),
    )
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_ocr_service] = lambda: service
    yield TestClient(app), service, db_session
    app.dependency_overrides.clear()


def test_get_job_status(api_client):
    client, service, db = api_client
    repo = OcrRepository(db)
    job = repo.create_job(record_id=10, user_id=1)
    db.commit()
    resp = client.get(f"/api/v1/ocr/jobs/{job.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "PENDING"


def test_get_job_not_found(api_client):
    client, _, _ = api_client
    resp = client.get("/api/v1/ocr/jobs/99999")
    assert resp.status_code == 404


@pytest.fixture
def api_reprocess(db_session):
    def _db():
        yield db_session

    def _user():
        return CurrentUser(id=1)

    # 원본 이미지 존재 여부는 서비스가 보유한 storage가 결정하므로 stub을 주입한다.
    storage = _FileStorageStub(exists_value=True)
    service = OcrService(
        ocr_repo=OcrRepository(db_session),
        record_repo=RecordRepository(db_session),
        ocr_client=StubOcrClient(),
        file_storage=storage,
        parser=OcrParser(),
    )

    async def _runner(job_id: int):
        await build_ocr_service(db_session).process_single(job_id)

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_ocr_service] = lambda: service
    app.dependency_overrides[get_ocr_job_runner] = lambda: _runner
    yield TestClient(app), db_session, storage
    app.dependency_overrides.clear()


def test_reprocess_rejects_when_image_missing(api_reprocess):
    client, db, storage = api_reprocess
    storage._exists_value = False

    repo = RecordRepository(db)
    record = repo.create_record(1, "UPLOAD", "some/path/image.png", "hashvalue")
    db.commit()

    resp = client.post(f"/api/v1/ocr/checkups/{record.id}/reprocess")
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "IMAGE_UNAVAILABLE"


def test_reprocess_triggers_when_image_exists(api_reprocess):
    client, db, storage = api_reprocess
    storage._exists_value = True

    repo = RecordRepository(db)
    record = repo.create_record(1, "UPLOAD", "some/path/image.png", "hashvalue2")
    db.commit()

    resp = client.post(f"/api/v1/ocr/checkups/{record.id}/reprocess")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "ocr_job_id" in data
    assert data["record_id"] == record.id
