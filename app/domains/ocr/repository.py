from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, SessionTransaction

from app.domains.ocr.models import OcrJob
from app.domains.ocr.status import OcrStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OcrRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_job(self, record_id: int, user_id: int) -> OcrJob:
        job = OcrJob(
            record_id=record_id,
            user_id=user_id,
            provider="CLOVA_GENERAL",
            status=OcrStatus.PENDING.value,
            requested_at=_now(),
        )
        self._db.add(job)
        self._db.flush()
        return job

    def get_job(self, job_id: int) -> OcrJob | None:
        return self._db.get(OcrJob, job_id)

    def get_job_fresh(self, job_id: int) -> OcrJob | None:
        stmt = (
            select(OcrJob)
            .where(OcrJob.id == job_id)
            .execution_options(populate_existing=True)
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def begin_nested(self) -> SessionTransaction:
        return self._db.begin_nested()

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()

    def claim_next_pending(self) -> OcrJob | None:
        # 단일 인스턴스 전제. 멀티 인스턴스 전환 시 with_for_update(skip_locked=True) 필요.
        stmt = (
            select(OcrJob)
            .where(OcrJob.status == OcrStatus.PENDING.value)
            .order_by(OcrJob.id)
            .limit(1)
        )
        job = self._db.execute(stmt).scalar_one_or_none()
        if job is None:
            return None
        job.status = OcrStatus.PROCESSING.value
        # requested_at를 처리 시작 시각으로 갱신한다(생성 시각은 created_at에 보존).
        # find_stuck_jobs가 '처리 시작 이후 경과'로 stuck을 판정하기 위함.
        job.requested_at = _now()
        self._db.flush()
        return job

    def mark_completed(
        self, job: OcrJob, raw_result_url: str | None, parsed_field_count: int
    ) -> None:
        job.status = OcrStatus.COMPLETED.value
        job.raw_result_url = raw_result_url
        job.parsed_field_count = parsed_field_count
        job.completed_at = _now()
        self._db.flush()

    def mark_failed(self, job: OcrJob, error_message: str) -> None:
        job.status = OcrStatus.FAILED.value
        job.error_message = error_message[:1000]
        job.completed_at = _now()
        self._db.flush()

    def find_stuck_jobs(self, timeout_seconds: int) -> list[OcrJob]:
        cutoff = _now() - timedelta(seconds=timeout_seconds)
        stmt = select(OcrJob).where(
            OcrJob.status == OcrStatus.PROCESSING.value,
            OcrJob.requested_at < cutoff,
        )
        return list(self._db.execute(stmt).scalars().all())
