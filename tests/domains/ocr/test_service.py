import pytest
from sqlalchemy.orm import Session

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

    async def recognize(self, image: bytes, image_format: str = "png") -> OcrResultDTO:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return self._result


class DeletingOcrClient:
    def __init__(self, record_repo, record, result):
        self._record_repo = record_repo
        self._record = record
        self._result = result

    async def recognize(self, image: bytes, image_format: str = "png") -> OcrResultDTO:
        self._record_repo.delete_record_cascade(self._record)
        return self._result


class ConcurrentDeletingOcrClient:
    def __init__(self, bind, record_id, result):
        self._bind = bind
        self._record_id = record_id
        self._result = result

    async def recognize(self, image: bytes, image_format: str = "png") -> OcrResultDTO:
        with Session(self._bind) as session:
            repo = RecordRepository(session)
            record = repo.get_record(self._record_id)
            assert record is not None
            repo.delete_record_cascade(record)
            session.commit()
        return self._result


class ConcurrentDeletingParser:
    def __init__(self, bind, record_id):
        self._bind = bind
        self._record_id = record_id
        self._parser = OcrParser()

    def parse(self, result):
        with Session(self._bind) as session:
            repo = RecordRepository(session)
            record = repo.get_record(self._record_id)
            assert record is not None
            repo.delete_record_cascade(record)
            session.commit()
        return self._parser.parse(result)


class SequenceOcrClient:
    def __init__(self, results):
        self._results = iter(results)

    async def recognize(self, image: bytes, image_format: str = "png") -> OcrResultDTO:
        return next(self._results)


class FakeFileStorage:
    def __init__(self, error=None):
        self._error = error
        self.uploads = []
        self.deletes = []

    async def upload(self, file_path: str, content: bytes) -> str:
        if self._error is not None:
            raise self._error
        self.uploads.append((file_path, content))
        return f"s3://{file_path}"

    async def read(self, path: str) -> bytes:
        return b"\x89PNG\r\n\x1a\n"

    async def exists(self, path: str) -> bool:
        return True

    async def delete(self, file_path: str) -> None:
        self.deletes.append(file_path)


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


def _make_service(db, client, storage=None, parser=None):
    return OcrService(
        ocr_repo=OcrRepository(db),
        record_repo=RecordRepository(db),
        ocr_client=client,
        file_storage=storage or FakeFileStorage(),
        parser=parser or OcrParser(),
        max_retries=2,
    )


@pytest.mark.asyncio
async def test_process_job_success_persists_metrics_and_deletes_image(db_session):
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
    assert storage.uploads == []
    metrics = {m.metric_code: m for m in record_repo.list_metrics(record.id)}
    assert metrics["fasting_glucose"].value == "109"
    assert record_repo.get_record(record.id).ocr_status == OcrStatus.COMPLETED.value
    assert "s3://a.png" in storage.deletes


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
    record_id = record.id
    job_id = job.id
    record_repo.delete_record_cascade(record)
    db_session.commit()

    await service.process_job(job)
    db_session.commit()

    assert service.get_job(job_id) is None
    assert client.calls == 0
    assert record_repo.list_metrics(record_id) == []


@pytest.mark.asyncio
async def test_process_job_skips_metrics_when_record_deleted_during_ocr(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    client = DeletingOcrClient(record_repo, record, _glucose_result())
    service = _make_service(db_session, client)
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()
    record_id = record.id
    job_id = job.id

    await service.process_job(job)
    db_session.commit()

    assert service.get_job(job_id) is None
    assert record_repo.list_metrics(record_id) == []


@pytest.mark.asyncio
async def test_concurrent_delete_during_ocr_is_idempotent(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    job = OcrRepository(db_session).create_job(record.id, user_id=1)
    db_session.commit()
    record_id = record.id
    job_id = job.id
    storage = FakeFileStorage()
    client = ConcurrentDeletingOcrClient(db_session.bind, record_id, _glucose_result())
    service = _make_service(db_session, client, storage)

    await service.process_job(job)
    db_session.commit()

    with Session(db_session.bind) as observer:
        assert observer.get(type(record), record_id) is None
        assert observer.get(type(job), job_id) is None
    assert storage.uploads == []
    assert storage.deletes == []


@pytest.mark.asyncio
async def test_database_flush_failure_is_persisted_as_failed(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    storage = FakeFileStorage()
    service = _make_service(
        db_session,
        FakeOcrClient(result=_oversized_glucose_result()),
        storage,
    )
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()

    await service.process_job(job)
    db_session.commit()

    assert job.status == OcrStatus.FAILED.value
    assert record_repo.get_record(record.id).ocr_status == OcrStatus.FAILED.value
    assert record_repo.list_metrics(record.id) == []
    assert storage.deletes == []  # failure path: image preserved, not deleted


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


@pytest.mark.asyncio
async def test_process_pending_commits_each_job_independently(db_session):
    record_repo = RecordRepository(db_session)
    first = record_repo.create_record(1, "UPLOAD", "s3://a.png", "a")
    second = record_repo.create_record(1, "UPLOAD", "s3://b.png", "b")
    db_session.commit()
    service = _make_service(
        db_session,
        SequenceOcrClient([_glucose_result(), _oversized_glucose_result()]),
    )
    first_job = await service.create_job(first.id, user_id=1)
    second_job = await service.create_job(second.id, user_id=1)
    db_session.commit()

    assert await service.process_pending() == 2

    with Session(db_session.bind) as observer:
        assert observer.get(type(first_job), first_job.id).status == OcrStatus.COMPLETED
        assert observer.get(type(second_job), second_job.id).status == OcrStatus.FAILED


@pytest.mark.asyncio
async def test_process_single_claims_and_deletes_image_on_success(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "checkups/1/h.png", "h")
    db_session.commit()
    storage = FakeFileStorage()  # read는 유효 PNG 바이트 반환하도록
    service = _make_service(db_session, FakeOcrClient(result=_glucose_result()), storage)
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()

    await service.process_single(job.id)

    assert service.get_job(job.id).status == OcrStatus.COMPLETED.value
    assert "checkups/1/h.png" in storage.deletes  # 성공 시 이미지 삭제


@pytest.mark.asyncio
async def test_process_single_skips_when_not_pending(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "checkups/1/h.png", "h")
    db_session.commit()
    service = _make_service(db_session, FakeOcrClient(result=_glucose_result()))
    job = await service.create_job(record.id, user_id=1)
    job.status = OcrStatus.COMPLETED.value  # 이미 완료된 잡
    db_session.commit()

    await service.process_single(job.id)  # 예외 없이 skip

    assert service.get_job(job.id).status == OcrStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_process_single_failure_persists_failed_status(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "checkups/1/h.png", "h")
    db_session.commit()

    class BoomClient:
        async def recognize(self, image: bytes, image_format: str = "png") -> OcrResultDTO:
            raise RuntimeError("ocr down")

    service = _make_service(db_session, BoomClient())
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()

    await service.process_single(job.id)

    # 별도 세션에서 커밋 여부 확인 — uncommitted flush라면 PROCESSING이 보인다
    with Session(db_session.bind) as observer:
        from app.domains.ocr.models import OcrJob

        assert observer.get(OcrJob, job.id).status == OcrStatus.FAILED.value
