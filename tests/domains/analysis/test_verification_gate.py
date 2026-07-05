from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ConflictException, NotFoundException
from app.domains.analysis.service import AnalysisService
from app.domains.record.repository import RecordRepository


def _service(record_repo: RecordRepository) -> AnalysisService:
    return AnalysisService(
        db=MagicMock(),
        analysis_repo=MagicMock(),
        record_repo=record_repo,
        mission_repo=MagicMock(),
        analysis_client=MagicMock(),
    )


def test_ensure_verified_blocks_unverified(db_session):
    repo = RecordRepository(db_session)
    record = repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()
    service = _service(repo)
    with pytest.raises(ConflictException) as exc_info:
        service.ensure_verified(record.id)
    assert exc_info.value.error_code == "NOT_VERIFIED"


def test_ensure_verified_passes_when_verified(db_session):
    repo = RecordRepository(db_session)
    record = repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    repo.set_verified(record)
    db_session.commit()
    service = _service(repo)
    service.ensure_verified(record.id)


def test_ensure_verified_missing_record_404(db_session):
    repo = RecordRepository(db_session)
    service = _service(repo)
    with pytest.raises(NotFoundException):
        service.ensure_verified(99999)
