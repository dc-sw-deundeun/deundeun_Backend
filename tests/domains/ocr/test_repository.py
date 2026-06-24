from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.status import OcrStatus


def test_create_job_sets_pending(db_session):
    repo = OcrRepository(db_session)
    job = repo.create_job(record_id=5, user_id=7, status=OcrStatus.PENDING.value)
    db_session.commit()
    assert job.id is not None
    assert job.status == OcrStatus.PENDING.value
    assert job.requested_at is not None


def test_create_job_with_final_status(db_session):
    from app.domains.record.repository import RecordRepository

    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD")
    db_session.commit()

    ocr_repo = OcrRepository(db_session)
    job = ocr_repo.create_job(
        record.id,
        1,
        status=OcrStatus.COMPLETED.value,
        parsed_field_count=5,
    )
    db_session.commit()

    assert job.status == OcrStatus.COMPLETED.value
    assert job.parsed_field_count == 5
    assert job.completed_at is not None
