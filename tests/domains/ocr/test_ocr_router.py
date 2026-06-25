import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.database.session import get_db
from app.domains.ocr.dependencies import get_ocr_service
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.record.repository import RecordRepository
from app.domains.user.schemas import CurrentUser
from app.infrastructure.ocr.ocr_client import StubOcrClient
from app.infrastructure.ocr.parser import OcrParser
from app.main import app


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
        parser=OcrParser(),
    )
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_ocr_service] = lambda: service
    yield TestClient(app), db_session
    app.dependency_overrides.clear()


def test_get_job_status(api_client):
    client, db = api_client
    repo = OcrRepository(db)
    job = repo.create_job(record_id=10, user_id=1, status="COMPLETED")
    db.commit()
    resp = client.get(f"/api/v1/ocr/jobs/{job.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "COMPLETED"


def test_get_job_not_found(api_client):
    client, _ = api_client
    resp = client.get("/api/v1/ocr/jobs/99999")
    assert resp.status_code == 404
