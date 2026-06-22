import pytest

from app.core.exceptions import ForbiddenException, NotFoundException
from app.domains.record.repository import RecordRepository
from app.domains.record.schemas import MetricUpdateItem
from app.domains.record.service import RecordService
from app.infrastructure.ocr.parser import ParsedMetric


class FakeFileStorage:
    def __init__(self):
        self.deleted = []

    async def upload(self, file_path, content):
        return f"s3://{file_path}"

    async def delete(self, file_path):
        self.deleted.append(file_path)


def _seed(db, user_id=1):
    repo = RecordRepository(db)
    record = repo.create_record(user_id, "UPLOAD", "s3://a.png", "h")
    db.commit()
    repo.upsert_ocr_metrics(record.id, [
        ParsedMetric(metric_code="bmi", metric_name="체질량지수",
                     value="24.1", unit="kg/m2", confidence=0.5, raw_text="24.1"),
    ])
    db.commit()
    return repo, record


def test_update_metric_sets_manual(db_session):
    repo, record = _seed(db_session)
    service = RecordService(repo, FakeFileStorage())
    metric = repo.list_metrics(record.id)[0]
    updated = service.update_metric(1, record.id, metric.id, "25.0", "kg/m2")
    db_session.commit()
    assert updated.value == "25.0"
    assert updated.source == "MANUAL"
    assert updated.is_edited is True


def test_update_metric_other_user_forbidden(db_session):
    repo, record = _seed(db_session, user_id=1)
    service = RecordService(repo, FakeFileStorage())
    metric = repo.list_metrics(record.id)[0]
    with pytest.raises(ForbiddenException):
        service.update_metric(999, record.id, metric.id, "25.0", None)


def test_verify_with_edits_marks_verified(db_session):
    repo, record = _seed(db_session)
    service = RecordService(repo, FakeFileStorage())
    metric = repo.list_metrics(record.id)[0]
    result = service.verify(1, record.id, [MetricUpdateItem(metric_id=metric.id, value="26.0")])
    db_session.commit()
    assert result.verification_status == "VERIFIED"
    assert repo.list_metrics(record.id)[0].value == "26.0"


def test_get_metrics_missing_record_404(db_session):
    repo = RecordRepository(db_session)
    service = RecordService(repo, FakeFileStorage())
    with pytest.raises(NotFoundException):
        service.get_metrics(1, 12345)


@pytest.mark.asyncio
async def test_delete_checkup_removes_files(db_session):
    repo, record = _seed(db_session)
    storage = FakeFileStorage()
    service = RecordService(repo, storage)
    await service.delete_checkup(1, record.id)
    db_session.commit()
    assert "s3://a.png" in storage.deleted
    assert repo.get_record(record.id) is None
