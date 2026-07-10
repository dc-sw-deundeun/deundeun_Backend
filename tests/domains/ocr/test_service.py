import asyncio

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import OcrBusyException, OcrFailedException
from app.domains.ocr.models import OcrJob
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import FinalMetric, OcrService, UploadOutcome
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


class _DelayedClient:
    def __init__(self) -> None:
        self.in_flight = 0
        self.max_in_flight = 0

    async def recognize(self, image: bytes, image_format: str = "png") -> OcrResultDTO:
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.01)
        self.in_flight -= 1
        return _glucose_result()


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
_HASH = "a" * 64


@pytest.mark.asyncio
async def test_process_upload_single_image_preview_success_without_db_write(db_session):
    service = _make_service(db_session, _SyncClient(result=_glucose_result()))
    outcome = await service.process_upload(user_id=1, images=[_PNG], content_hash=_HASH)

    assert isinstance(outcome, UploadOutcome)
    assert outcome.page_count == 1
    assert outcome.failed_pages == []
    assert outcome.ocr_status == OcrStatus.COMPLETED.value
    glucose = next(metric for metric in outcome.metrics if metric.metric_code == "fasting_glucose")
    assert glucose.page_index == 0
    assert glucose.value == "109"
    assert db_session.query(CheckupRecord).all() == []
    assert db_session.query(OcrJob).all() == []


@pytest.mark.asyncio
async def test_process_upload_ten_images_creates_merged_preview_metrics(db_session):
    service = _make_service(db_session, _SyncClient(result=_glucose_result()))
    outcome = await service.process_upload(user_id=1, images=[_PNG] * 10, content_hash=_HASH)

    assert outcome.page_count == 10
    assert outcome.failed_pages == []
    glucose_rows = [metric for metric in outcome.metrics if metric.metric_code == "fasting_glucose"]
    assert len(glucose_rows) == 1
    assert db_session.query(CheckupRecord).all() == []


@pytest.mark.asyncio
async def test_process_upload_partial_failure_preview(db_session):
    client = _PerPageClient([_glucose_result(), RuntimeError("clova timeout"), _bmi_result()])
    service = _make_service(db_session, client)
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG, _PNG], content_hash=_HASH)

    assert outcome.page_count == 3
    assert outcome.failed_pages == [1]
    assert outcome.ocr_status == OcrStatus.PARTIAL.value
    codes = {metric.metric_code for metric in outcome.metrics}
    assert "fasting_glucose" in codes
    assert "bmi" in codes
    assert db_session.query(CheckupRecord).all() == []


@pytest.mark.asyncio
async def test_process_upload_all_fail_raises_ocr_failed_without_db_write(db_session):
    service = _make_service(db_session, _SyncClient(error=RuntimeError("clova down")))

    with pytest.raises(OcrFailedException):
        await service.process_upload(user_id=1, images=[_PNG, _PNG], content_hash=_HASH)

    assert db_session.query(CheckupRecord).filter(CheckupRecord.user_id == 1).all() == []
    assert db_session.query(OcrJob).all() == []


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
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG], content_hash=_HASH)

    glucose = next(metric for metric in outcome.metrics if metric.metric_code == "fasting_glucose")
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
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG], content_hash=_HASH)

    glucose = next(metric for metric in outcome.metrics if metric.metric_code == "fasting_glucose")
    assert glucose.value == "80"
    assert glucose.page_index == 0


def test_commit_upload_writes_record_metrics_and_audit_job(db_session):
    service = _make_service(db_session, _SyncClient(result=_glucose_result()))
    outcome = service.commit_upload(
        user_id=1,
        ocr_status=OcrStatus.PARTIAL.value,
        failed_pages=[1],
        content_hash=_HASH,
        metrics=[
            FinalMetric(
                metric_code="fasting_glucose",
                metric_name="공복혈당",
                value="105",
                unit="mg/dL",
                confidence=0.91,
                raw_text="109",
                page_index=0,
                is_edited=True,
            )
        ],
    )

    jobs = db_session.query(OcrJob).filter(OcrJob.record_id == outcome.record_id).all()
    assert len(jobs) == 1
    assert jobs[0].status == OcrStatus.PARTIAL.value
    assert jobs[0].error_message == "pages [1] failed"
    assert jobs[0].completed_at is not None
    record = db_session.get(CheckupRecord, outcome.record_id)
    assert record is not None
    assert record.verification_status == "UNVERIFIED"
    assert outcome.metrics[0].value == "105"
    assert outcome.metrics[0].is_edited is True


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
    outcome = await service.process_upload(user_id=1, images=[_PNG], content_hash=_HASH)

    assert outcome.failed_pages == []
    assert call_count == 2


@pytest.mark.asyncio
async def test_process_upload_respects_concurrency_limit(db_session):
    client = _DelayedClient()
    service = _make_service(db_session, client, concurrency=2)

    await service.process_upload(user_id=1, images=[_PNG] * 5, content_hash=_HASH)

    assert client.max_in_flight == 2


@pytest.mark.asyncio
async def test_process_upload_raises_ocr_busy_when_global_capacity_full(db_session):
    limiter = asyncio.Semaphore(1)
    await limiter.acquire()
    service = OcrService(
        ocr_repo=OcrRepository(db_session),
        record_repo=RecordRepository(db_session),
        ocr_client=_SyncClient(result=_glucose_result()),
        parser=OcrParser(),
        max_retries=0,
        concurrency=1,
        global_limiter=limiter,
        acquire_timeout_seconds=0.01,
        retry_after_seconds=10,
    )

    with pytest.raises(OcrBusyException) as exc_info:
        await service.process_upload(user_id=1, images=[_PNG], content_hash=_HASH)

    limiter.release()
    assert exc_info.value.retry_after_seconds == 10
    assert db_session.query(CheckupRecord).all() == []


def test_commit_upload_rolls_back_when_metric_insert_fails(db_session):
    service = _make_service(db_session, _SyncClient(result=_glucose_result()))

    with pytest.raises(SQLAlchemyError):
        service.commit_upload(
            user_id=1,
            ocr_status=OcrStatus.COMPLETED.value,
            failed_pages=[],
            content_hash=_HASH,
            metrics=[
                FinalMetric(
                    metric_code="invalid_metric",
                    metric_name="x" * 101,
                    value="1",
                    unit="",
                    confidence=0.9,
                    raw_text="1",
                    page_index=0,
                )
            ],
        )

    db_session.rollback()
    assert db_session.query(CheckupRecord).filter(CheckupRecord.user_id == 1).all() == []
    assert db_session.query(OcrJob).all() == []


def _empty_result() -> OcrResultDTO:
    return OcrResultDTO(fields=[])


@pytest.mark.asyncio
async def test_pages_without_metrics_when_all_metrics_empty(db_session):
    # All pages yield no metrics → every page index is in pages_without_metrics
    client = _PerPageClient([_empty_result(), _empty_result(), _empty_result()])
    service = _make_service(db_session, client)
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG, _PNG], content_hash=_HASH)

    assert outcome.pages_without_metrics == [0, 1, 2]
    assert outcome.metrics == []
    assert outcome.ocr_status == OcrStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_some_pages_without_metrics(db_session):
    # Page 0 yields metrics, page 1 yields nothing
    client = _PerPageClient([_glucose_result(), _empty_result()])
    service = _make_service(db_session, client)
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG], content_hash=_HASH)

    assert outcome.pages_without_metrics == [1]
    codes = {metric.metric_code for metric in outcome.metrics}
    assert "fasting_glucose" in codes


@pytest.mark.asyncio
async def test_failed_pages_and_empty_pages_are_separate(db_session):
    # Page 0 succeeds with metrics, page 1 fails OCR, page 2 succeeds but yields no metrics
    client = _PerPageClient([_glucose_result(), RuntimeError("ocr error"), _empty_result()])
    service = _make_service(db_session, client)
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG, _PNG], content_hash=_HASH)

    assert outcome.failed_pages == [1]
    assert outcome.pages_without_metrics == [2]
    assert outcome.ocr_status == OcrStatus.PARTIAL.value
    codes = {metric.metric_code for metric in outcome.metrics}
    assert "fasting_glucose" in codes


@pytest.mark.asyncio
async def test_ocr_status_unaffected_by_pages_without_metrics(db_session):
    # pages_without_metrics present but failed_pages empty → ocr_status must be COMPLETED
    client = _PerPageClient([_glucose_result(), _empty_result()])
    service = _make_service(db_session, client)
    outcome = await service.process_upload(user_id=1, images=[_PNG, _PNG], content_hash=_HASH)

    assert outcome.pages_without_metrics == [1]
    assert outcome.failed_pages == []
    assert outcome.ocr_status == OcrStatus.COMPLETED.value
