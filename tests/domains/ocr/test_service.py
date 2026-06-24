import pytest

from app.core.exceptions import OcrFailedException
from app.domains.ocr.models import OcrJob
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService, UploadOutcome
from app.domains.ocr.status import OcrStatus
from app.domains.record.models import CheckupRecord
from app.domains.record.repository import RecordRepository
from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser


def _glucose_result(confidence: float = 0.95) -> OcrResultDTO:
    return OcrResultDTO(
        fields=[
            OcrFieldDTO(text="공복혈당", confidence=confidence, x_min=10, x_max=40, y_center=100),
            OcrFieldDTO(text="109", confidence=confidence, x_min=120, x_max=150, y_center=100),
        ]
    )


def _bmi_result(confidence: float = 0.9) -> OcrResultDTO:
    return OcrResultDTO(
        fields=[
            OcrFieldDTO(text="체질량지수", confidence=confidence, x_min=10, x_max=50, y_center=100),
            OcrFieldDTO(text="24.1", confidence=confidence, x_min=120, x_max=150, y_center=100),
        ]
    )


class _SyncClient:
    def __init__(self, result: OcrResultDTO | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: int = 0

    async def recognize(self, image: bytes, image_format: str = "png") -> OcrResultDTO:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class _PerPageClient:
    def __init__(self, results: list[OcrResultDTO | Exception]) -> None:
        self._results = results
        self._idx = 0

    async def recognize(self, image: bytes, image_format: str = "png") -> OcrResultDTO:
        result = self._results[self._idx]
        self._idx += 1
        if isinstance(result, Exception):
            raise result
        return result


def _make_service(db, client, *, max_retries: int = 0, concurrency: int = 5) -> OcrService:
    return OcrService(
        ocr_repo=OcrRepository(db),
        record_repo=RecordRepository(db),
        ocr_client=client,
        parser=OcrParser(),
        max_retries=max_retries,
        concurrency=concurrency,
    )


_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.mark.asyncio
async def test_process_upload_single_image_success(db_session):
    service = _make_service(db_session, _SyncClient(result=_glucose_result()))
    outcome = await service.process_upload(user_id=1, images=[_PNG])

    assert isinstance(outcome, UploadOutcome)
    assert outcome.page_count == 1
    assert outcome.failed_pages == []
    assert outcome.ocr_status == OcrStatus.COMPLETED.value

    record_repo = RecordRepository(db_session)
    metrics = record_repo.list_metrics(outcome.record_id)
    assert any(metric.metric_code == "fasting_glucose" for metric in metrics)
    glucose = next(metric for metric in metrics if metric.metric_code == "fasting_glucose")
    assert glucose.page_index == 0
    assert glucose.value == "109"

    record = record_repo.get_record(outcome.record_id)
    assert record is not None
    assert record.file_url is None
    assert record.file_hash is None


@pytest.mark.asyncio
async def test_process_upload_ten_images_creates_merged_metrics(db_session):
    service = _make_service(db_session, _SyncClient(result=_glucose_result()))
    outcome = await service.process_upload(user_id=1, images=[_PNG] * 10)

    assert outcome.page_count == 10
    assert outcome.failed_pages == []
    metrics = RecordRepository(db_session).list_metrics(outcome.record_id)
    glucose_rows = [metric for metric in metrics if metric.metric_code == "fasting_glucose"]
    assert len(glucose_rows) == 1


@pytest.mark.asyncio
async def test_process_upload_partial_failure(db_session):
    client = _PerPageClient([_glucose_result(), RuntimeError("clova timeout"), _bmi_result()])
    service = _make_service(db_session, client)
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG, _PNG])

    assert outcome.page_count == 3
    assert outcome.failed_pages == [1]
    assert outcome.ocr_status == OcrStatus.PARTIAL.value

    codes = {
        metric.metric_code
        for metric in RecordRepository(db_session).list_metrics(outcome.record_id)
    }
    assert "fasting_glucose" in codes
    assert "bmi" in codes


@pytest.mark.asyncio
async def test_process_upload_all_fail_raises_ocr_failed(db_session):
    service = _make_service(db_session, _SyncClient(error=RuntimeError("clova down")))

    with pytest.raises(OcrFailedException):
        await service.process_upload(user_id=1, images=[_PNG, _PNG])

    records = db_session.query(CheckupRecord).filter(CheckupRecord.user_id == 1).all()
    assert records == []


@pytest.mark.asyncio
async def test_merge_higher_confidence_wins(db_session):
    client = _PerPageClient(
        [
            OcrResultDTO(
                fields=[
                    OcrFieldDTO(text="공복혈당", confidence=0.5, x_min=10, x_max=40, y_center=100),
                    OcrFieldDTO(text="80", confidence=0.5, x_min=120, x_max=150, y_center=100),
                ]
            ),
            OcrResultDTO(
                fields=[
                    OcrFieldDTO(text="공복혈당", confidence=0.95, x_min=10, x_max=40, y_center=100),
                    OcrFieldDTO(text="109", confidence=0.95, x_min=120, x_max=150, y_center=100),
                ]
            ),
        ]
    )
    service = _make_service(db_session, client)
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG])

    metrics = RecordRepository(db_session).list_metrics(outcome.record_id)
    glucose = next(metric for metric in metrics if metric.metric_code == "fasting_glucose")
    assert glucose.value == "109"
    assert glucose.page_index == 1


@pytest.mark.asyncio
async def test_merge_tie_first_page_wins(db_session):
    client = _PerPageClient(
        [
            OcrResultDTO(
                fields=[
                    OcrFieldDTO(text="공복혈당", confidence=0.9, x_min=10, x_max=40, y_center=100),
                    OcrFieldDTO(text="80", confidence=0.9, x_min=120, x_max=150, y_center=100),
                ]
            ),
            OcrResultDTO(
                fields=[
                    OcrFieldDTO(text="공복혈당", confidence=0.9, x_min=10, x_max=40, y_center=100),
                    OcrFieldDTO(text="109", confidence=0.9, x_min=120, x_max=150, y_center=100),
                ]
            ),
        ]
    )
    service = _make_service(db_session, client)
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG])

    metrics = RecordRepository(db_session).list_metrics(outcome.record_id)
    glucose = next(metric for metric in metrics if metric.metric_code == "fasting_glucose")
    assert glucose.value == "80"
    assert glucose.page_index == 0


@pytest.mark.asyncio
async def test_audit_job_row_written(db_session):
    service = _make_service(db_session, _SyncClient(result=_glucose_result()))
    outcome = await service.process_upload(user_id=1, images=[_PNG])

    jobs = db_session.query(OcrJob).filter(OcrJob.record_id == outcome.record_id).all()
    assert len(jobs) == 1
    assert jobs[0].status == OcrStatus.COMPLETED.value
    assert jobs[0].completed_at is not None


@pytest.mark.asyncio
async def test_partial_audit_job_error_message(db_session):
    client = _PerPageClient([_glucose_result(), RuntimeError("timeout")])
    service = _make_service(db_session, client)
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG])

    job = db_session.query(OcrJob).filter(OcrJob.record_id == outcome.record_id).first()
    assert job is not None
    assert job.status == OcrStatus.PARTIAL.value
    assert job.error_message is not None
    assert "1" in job.error_message


@pytest.mark.asyncio
async def test_retry_on_transient_error(db_session):
    call_count = 0

    class _RetryClient:
        async def recognize(self, image: bytes, image_format: str = "png") -> OcrResultDTO:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient")
            return _glucose_result()

    service = _make_service(db_session, _RetryClient(), max_retries=1)
    outcome = await service.process_upload(user_id=1, images=[_PNG])

    assert outcome.failed_pages == []
    assert call_count == 2
