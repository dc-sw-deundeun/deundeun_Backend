import pytest

from app.core.exceptions import ConflictException, NotFoundException
from app.domains.analysis.service import AnalysisService
from app.domains.record.repository import RecordRepository


def test_ensure_verified_blocks_unverified(db_session):
    repo = RecordRepository(db_session)
    record = repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    db_session.commit()  # 기본 UNVERIFIED
    service = AnalysisService(record_repo=repo)
    with pytest.raises(ConflictException):
        service.ensure_verified(record.id)


def test_ensure_verified_passes_when_verified(db_session):
    repo = RecordRepository(db_session)
    record = repo.create_record(1, "UPLOAD", "s3://a.png", "h")
    repo.set_verified(record)
    db_session.commit()
    service = AnalysisService(record_repo=repo)
    service.ensure_verified(record.id)  # 예외 없음


def test_ensure_verified_missing_record_404(db_session):
    repo = RecordRepository(db_session)
    service = AnalysisService(record_repo=repo)
    with pytest.raises(NotFoundException):
        service.ensure_verified(99999)
