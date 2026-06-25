from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domains.ocr.models import OcrJob
from app.domains.ocr.status import OcrStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OcrRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_job(
        self,
        record_id: int,
        user_id: int,
        *,
        status: str,
        parsed_field_count: int | None = None,
        error_message: str | None = None,
    ) -> OcrJob:
        valid_statuses = {s.value for s in OcrStatus}
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid OcrStatus: {status!r}. Must be one of {sorted(valid_statuses)}"
            )
        now = _now()
        terminal = {OcrStatus.COMPLETED.value, OcrStatus.PARTIAL.value, OcrStatus.FAILED.value}
        job = OcrJob(
            record_id=record_id,
            user_id=user_id,
            provider="CLOVA_GENERAL",
            status=status,
            requested_at=now,
            completed_at=now if status in terminal else None,
            parsed_field_count=parsed_field_count,
            error_message=error_message[:1000] if error_message else None,
        )
        self._db.add(job)
        self._db.flush()
        return job

    def get_job(self, job_id: int) -> OcrJob | None:
        return self._db.get(OcrJob, job_id)

    def commit(self) -> None:
        self._db.commit()

    def rollback(self) -> None:
        self._db.rollback()
