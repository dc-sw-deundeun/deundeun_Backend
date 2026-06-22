from app.domains.ocr.models import OcrJob
from app.domains.record.models import CheckupMetricResult
from app.domains.record.repository import RecordRepository
from app.infrastructure.ocr.parser import ParsedMetric


def _parsed(code, value):
    return ParsedMetric(
        metric_code=code,
        metric_name=code,
        value=value,
        unit="x",
        confidence=0.9,
        raw_text=value,
    )


def test_create_and_get_record(db_session):
    repo = RecordRepository(db_session)
    record = repo.create_record(1, "UPLOAD", "s3://a.png", "hash1")
    db_session.commit()
    assert repo.get_record(record.id).file_hash == "hash1"


def test_find_by_user_and_hash(db_session):
    repo = RecordRepository(db_session)
    repo.create_record(1, "UPLOAD", "s3://a.png", "hash1")
    db_session.commit()
    assert repo.find_by_user_and_hash(1, "hash1") is not None
    assert repo.find_by_user_and_hash(1, "nope") is None


def test_upsert_preserves_manual_edits(db_session):
    repo = RecordRepository(db_session)
    record = repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    repo.upsert_ocr_metrics(record.id, [_parsed("bmi", "24.1"), _parsed("hdl", "66")])
    db_session.commit()
    bmi = next(m for m in repo.list_metrics(record.id) if m.metric_code == "bmi")
    repo.update_metric_value(bmi, "25.0", "kg/m2")
    db_session.commit()
    repo.upsert_ocr_metrics(record.id, [_parsed("bmi", "99.9"), _parsed("hdl", "70")])
    db_session.commit()
    metrics = {m.metric_code: m for m in repo.list_metrics(record.id)}
    assert metrics["bmi"].value == "25.0"
    assert metrics["bmi"].source == "MANUAL"
    assert metrics["hdl"].value == "70"


def test_delete_record_cascade_returns_file_urls(db_session):
    repo = RecordRepository(db_session)
    record = repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    db_session.add(
        OcrJob(
            record_id=record.id,
            user_id=1,
            provider="CLOVA_GENERAL",
            status="COMPLETED",
            raw_result_url="s3://raw.json",
        )
    )
    db_session.add(
        CheckupMetricResult(
            record_id=record.id,
            metric_code="bmi",
            metric_name="bmi",
            value="24.1",
            source="OCR",
            is_edited=False,
        )
    )
    db_session.commit()
    urls = repo.delete_record_cascade(record)
    db_session.commit()
    assert "s3://a.png" in urls
    assert "s3://raw.json" in urls
    assert repo.get_record(record.id) is None
    assert repo.list_metrics(record.id) == []
