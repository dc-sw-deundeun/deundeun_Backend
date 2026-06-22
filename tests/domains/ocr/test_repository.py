from datetime import datetime, timedelta, timezone

from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.status import OcrStatus


def test_create_job_sets_pending(db_session):
    repo = OcrRepository(db_session)
    job = repo.create_job(record_id=5, user_id=7)
    db_session.commit()
    assert job.id is not None
    assert job.status == OcrStatus.PENDING.value
    assert job.requested_at is not None


def test_claim_next_pending_transitions_to_processing(db_session):
    repo = OcrRepository(db_session)
    repo.create_job(record_id=1, user_id=1)
    db_session.commit()
    claimed = repo.claim_next_pending()
    db_session.commit()
    assert claimed.status == OcrStatus.PROCESSING.value


def test_claim_next_pending_returns_none_when_empty(db_session):
    repo = OcrRepository(db_session)
    assert repo.claim_next_pending() is None


def test_mark_completed(db_session):
    repo = OcrRepository(db_session)
    job = repo.create_job(record_id=1, user_id=1)
    db_session.commit()
    repo.mark_completed(job, raw_result_url="s3://raw.json", parsed_field_count=9)
    db_session.commit()
    assert job.status == OcrStatus.COMPLETED.value
    assert job.parsed_field_count == 9
    assert job.completed_at is not None


def test_find_stuck_jobs(db_session):
    repo = OcrRepository(db_session)
    job = repo.create_job(record_id=1, user_id=1)
    job.status = OcrStatus.PROCESSING.value
    job.requested_at = datetime.now(timezone.utc) - timedelta(seconds=600)
    db_session.commit()
    stuck = repo.find_stuck_jobs(timeout_seconds=300)
    assert job.id in {j.id for j in stuck}
