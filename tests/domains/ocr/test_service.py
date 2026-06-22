import pytest

from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.ocr.status import OcrStatus
from app.domains.record.repository import RecordRepository
from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser


class FakeOcrClient:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = 0

    async def recognize(self, file_url: str) -> OcrResultDTO:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._result


class DeletingOcrClient:
    def __init__(self, record_repo, record, result):
        self._record_repo = record_repo
        self._record = record
        self._result = result

    async def recognize(self, file_url: str) -> OcrResultDTO:
        self._record_repo.delete_record_cascade(self._record)
        return self._result


class FakeFileStorage:
    def __init__(self, error=None):
        self._error = error
        self.uploads = []

    async def upload(self, file_path: str, content: bytes) -> str:
        if self._error is not None:
            raise self._error
        self.uploads.append((file_path, content))
        return f"s3://{file_path}"

    async def delete(self, file_path: str) -> None:
        return None


def _glucose_result():
    return OcrResultDTO(
        fields=[
            OcrFieldDTO(
                text="공복혈당",
                confidence=0.97,
                x_min=10,
                x_max=40,
                y_center=100,
            ),
            OcrFieldDTO(
                text="109",
                confidence=0.95,
                x_min=120,
                x_max=150,
                y_center=100,
            ),
        ]
    )


def _oversized_glucose_result():
    result = _glucose_result()
    result.fields[1].text = "1" * 51
    return result


def _make_service(db, client, storage=None):
    return OcrService(
        ocr_repo=OcrRepository(db),
        record_repo=RecordRepository(db),
        ocr_client=client,
        file_storage=storage or FakeFileStorage(),
        parser=OcrParser(),
        max_retries=2,
    )


@pytest.mark.asyncio
async def test_process_job_success_persists_metrics_and_raw_result(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    storage = FakeFileStorage()
    service = _make_service(db_session, FakeOcrClient(result=_glucose_result()), storage)
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()

    await service.process_job(job)
    db_session.commit()

    assert job.status == OcrStatus.COMPLETED.value
    assert job.raw_result_url == f"s3://ocr/raw/{job.id}.json"
    assert storage.uploads[0][0] == f"ocr/raw/{job.id}.json"
    assert b'"fields"' in storage.uploads[0][1]
    metrics = {m.metric_code: m for m in record_repo.list_metrics(record.id)}
    assert metrics["fasting_glucose"].value == "109"
    assert record_repo.get_record(record.id).ocr_status == OcrStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_process_job_failure_marks_failed_after_retries(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    client = FakeOcrClient(error=RuntimeError("clova down"))
    service = _make_service(db_session, client)
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()

    await service.process_job(job)
    db_session.commit()

    assert job.status == OcrStatus.FAILED.value
    assert client.calls == 3
    assert record_repo.get_record(record.id).ocr_status == OcrStatus.FAILED.value


@pytest.mark.asyncio
async def test_process_job_skips_when_record_deleted(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    client = FakeOcrClient(result=_glucose_result())
    service = _make_service(db_session, client)
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()
    record_repo.delete_record_cascade(record)
    db_session.commit()

    await service.process_job(job)
    db_session.commit()

    assert job.status == OcrStatus.FAILED.value
    assert client.calls == 0
    assert record_repo.list_metrics(record.id) == []


@pytest.mark.asyncio
async def test_process_job_skips_metrics_when_record_deleted_during_ocr(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    client = DeletingOcrClient(record_repo, record, _glucose_result())
    service = _make_service(db_session, client)
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()

    await service.process_job(job)
    db_session.commit()

    assert job.status == OcrStatus.FAILED.value
    assert record_repo.list_metrics(record.id) == []


@pytest.mark.asyncio
async def test_raw_storage_failure_does_not_fail_processing(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    storage = FakeFileStorage(error=RuntimeError("storage unavailable"))
    service = _make_service(db_session, FakeOcrClient(result=_glucose_result()), storage)
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()

    await service.process_job(job)
    db_session.commit()

    assert job.status == OcrStatus.COMPLETED.value
    assert job.raw_result_url is None
    assert len(record_repo.list_metrics(record.id)) == 1


@pytest.mark.asyncio
async def test_database_flush_failure_is_persisted_as_failed(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    service = _make_service(db_session, FakeOcrClient(result=_oversized_glucose_result()))
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()

    await service.process_job(job)
    db_session.commit()

    assert job.status == OcrStatus.FAILED.value
    assert record_repo.get_record(record.id).ocr_status == OcrStatus.FAILED.value
    assert record_repo.list_metrics(record.id) == []


@pytest.mark.asyncio
async def test_process_pending_claims_all_jobs_and_get_job(db_session):
    record_repo = RecordRepository(db_session)
    first = record_repo.create_record(1, "UPLOAD", "s3://a.png", "a")
    second = record_repo.create_record(1, "UPLOAD", "s3://b.png", "b")
    db_session.commit()
    service = _make_service(db_session, FakeOcrClient(result=_glucose_result()))
    first_job = await service.create_job(first.id, user_id=1)
    second_job = await service.create_job(second.id, user_id=1)
    db_session.commit()

    processed = await service.process_pending()
    db_session.commit()

    assert processed == 2
    assert service.get_job(first_job.id).status == OcrStatus.COMPLETED.value
    assert service.get_job(second_job.id).status == OcrStatus.COMPLETED.value
