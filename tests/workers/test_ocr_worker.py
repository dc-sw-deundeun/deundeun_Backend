from datetime import datetime, timedelta, timezone

import pytest

from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.ocr.status import OcrStatus
from app.domains.record.repository import RecordRepository
from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser
from app.workers.ocr_worker import recover_stuck, run_ocr_batch


class FakeClient:
    async def recognize(self, file_url):
        return OcrResultDTO(fields=[
            OcrFieldDTO(text="공복혈당", confidence=0.9, x_min=10, x_max=40, y_center=10),
            OcrFieldDTO(text="109", confidence=0.9, x_min=120, x_max=150, y_center=10),
        ])


class FakeStorage:
    async def upload(self, p, c):
        return f"s3://{p}"

    async def delete(self, p):
        return None


def test_recover_stuck_marks_failed(db_session):
    repo = OcrRepository(db_session)
    job = repo.create_job(record_id=1, user_id=1)
    job.status = OcrStatus.PROCESSING.value
    job.requested_at = datetime.now(timezone.utc) - timedelta(seconds=600)
    db_session.commit()
    count = recover_stuck(repo, stuck_timeout_seconds=300)
    db_session.commit()
    assert count == 1
    assert repo.get_job(job.id).status == OcrStatus.FAILED.value


@pytest.mark.asyncio
async def test_run_ocr_batch_processes_pending(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    ocr_repo = OcrRepository(db_session)
    service = OcrService(
        ocr_repo=ocr_repo, record_repo=record_repo, ocr_client=FakeClient(),
        file_storage=FakeStorage(), parser=OcrParser(),
    )
    ocr_repo.create_job(record.id, 1)
    db_session.commit()
    processed = await run_ocr_batch(service, ocr_repo, stuck_timeout_seconds=300)
    db_session.commit()
    assert processed == 1
    metrics = {m.metric_code for m in record_repo.list_metrics(record.id)}
    assert "fasting_glucose" in metrics
