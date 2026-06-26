from datetime import datetime, timezone

from app.domains.ocr.models import OcrJob
from app.domains.ocr.status import OcrStatus
from app.domains.record.models import CheckupMetricResult, CheckupRecord


def test_can_persist_record_with_new_columns(db_session):
    record = CheckupRecord(
        user_id=1,
        source_type="UPLOAD",
        file_url="s3://a.png",
        file_hash="abc",
        ocr_status=OcrStatus.PENDING.value,
        verification_status="UNVERIFIED",
        analysis_status="PENDING",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(record)
    db_session.commit()
    assert record.id is not None


def test_can_persist_ocr_job(db_session):
    job = OcrJob(
        record_id=1,
        user_id=1,
        provider="CLOVA_GENERAL",
        status=OcrStatus.PENDING.value,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    db_session.commit()
    assert job.id is not None


def test_can_persist_metric_with_source(db_session):
    metric = CheckupMetricResult(
        record_id=1,
        metric_code="bmi",
        metric_name="체질량지수",
        value="24.1",
        unit="kg/m2",
        source="OCR",
        confidence=0.9,
        is_edited=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(metric)
    db_session.commit()
    assert metric.id is not None
