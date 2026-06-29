from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.analysis.models import (
    AnalysisJob,
    AnalysisMissionCandidate,
    CheckupAnalysisSummary,
)
from app.domains.analysis.status import AnalysisStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def commit(self) -> None:
        self._db.commit()

    def flush(self) -> None:
        self._db.flush()

    def save_job(self, job: AnalysisJob) -> AnalysisJob:
        self._db.add(job)
        self._db.flush()
        return job

    def find_job_by_id(self, job_id: int) -> AnalysisJob | None:
        return self._db.get(AnalysisJob, job_id)

    def find_job_by_external_id(self, external_job_id: str) -> AnalysisJob | None:
        return self._db.scalar(
            select(AnalysisJob).where(AnalysisJob.external_job_id == external_job_id)
        )

    def find_latest_job_by_record_id(self, record_id: int) -> AnalysisJob | None:
        return self._db.scalar(
            select(AnalysisJob)
            .where(AnalysisJob.record_id == record_id)
            .order_by(AnalysisJob.created_at.desc())
            .limit(1)
        )

    def update_job_status(
        self,
        job: AnalysisJob,
        status: str,
        *,
        error_code: str | None = None,
        model_version: str | None = None,
        raw_result: dict | None = None,
        finished: bool = False,
    ) -> None:
        job.status = status
        if status == AnalysisStatus.COMPLETED.value:
            job.error_code = None
        if error_code is not None:
            job.error_code = error_code
        if model_version is not None:
            job.model_version = model_version
        if raw_result is not None:
            job.raw_result = raw_result
        if finished:
            job.finished_at = _now()
        self._db.flush()

    def save_summary(self, summary: CheckupAnalysisSummary) -> CheckupAnalysisSummary:
        try:
            with self._db.begin_nested():
                self._db.add(summary)
                self._db.flush()
            return summary
        except IntegrityError:
            existing = self.find_summary_by_record_id(summary.record_id)
            if existing is not None:
                return existing
            raise

    def find_summary_by_record_id(self, record_id: int) -> CheckupAnalysisSummary | None:
        return self._db.scalar(
            select(CheckupAnalysisSummary).where(CheckupAnalysisSummary.record_id == record_id)
        )

    def save_mission_candidate(self, candidate: AnalysisMissionCandidate) -> None:
        self._db.add(candidate)
        self._db.flush()

    def list_mission_candidates(self, summary_id: int) -> list[AnalysisMissionCandidate]:
        return list(
            self._db.scalars(
                select(AnalysisMissionCandidate).where(
                    AnalysisMissionCandidate.summary_id == summary_id
                )
            ).all()
        )

    def find_pending_jobs(self) -> list[AnalysisJob]:
        return list(
            self._db.scalars(
                select(AnalysisJob).where(
                    AnalysisJob.status.in_(
                        [AnalysisStatus.PENDING.value, AnalysisStatus.PROCESSING.value]
                    )
                )
            ).all()
        )
