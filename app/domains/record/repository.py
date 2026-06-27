from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.ocr.models import OcrJob
from app.domains.ocr.status import MetricSource, VerificationStatus
from app.domains.record.models import CheckupMetricResult, CheckupRecord
from app.infrastructure.ocr.parser import ParsedMetric


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RecordRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def commit(self) -> None:
        self._db.commit()

    def create_record(
        self,
        user_id: int,
        source_type: str,
        file_url: str | None = None,
        file_hash: str | None = None,
        ocr_status: str = "PENDING",
    ) -> CheckupRecord:
        record = CheckupRecord(
            user_id=user_id,
            source_type=source_type,
            file_url=file_url,
            file_hash=file_hash,
            ocr_status=ocr_status,
            verification_status=VerificationStatus.UNVERIFIED.value,
            analysis_status="PENDING",
        )
        self._db.add(record)
        self._db.flush()
        return record

    def get_record(self, record_id: int) -> CheckupRecord | None:
        return self._db.get(CheckupRecord, record_id)

    def find_by_user_and_hash(self, user_id: int, file_hash: str) -> CheckupRecord | None:
        return self._db.scalar(
            select(CheckupRecord).where(
                CheckupRecord.user_id == user_id,
                CheckupRecord.file_hash == file_hash,
            )
        )

    def list_checkups_by_user(
        self, user_id: int, *, offset: int, limit: int
    ) -> tuple[list[CheckupRecord], int]:
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(CheckupRecord)
                .where(CheckupRecord.user_id == user_id)
            )
            or 0
        )
        rows = self._db.scalars(
            select(CheckupRecord)
            .where(CheckupRecord.user_id == user_id)
            .order_by(CheckupRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), total

    def count_metrics(self, record_id: int) -> int:
        return (
            self._db.scalar(
                select(func.count())
                .select_from(CheckupMetricResult)
                .where(CheckupMetricResult.record_id == record_id)
            )
            or 0
        )

    def list_trend_series(
        self, user_id: int, metric_codes: list[str]
    ) -> list[tuple[CheckupRecord, CheckupMetricResult]]:
        if not metric_codes:
            return []
        stmt = (
            select(CheckupRecord, CheckupMetricResult)
            .join(
                CheckupMetricResult,
                CheckupMetricResult.record_id == CheckupRecord.id,
            )
            .where(
                CheckupRecord.user_id == user_id,
                CheckupMetricResult.metric_code.in_(metric_codes),
            )
            .order_by(CheckupRecord.created_at.asc(), CheckupMetricResult.metric_code.asc())
        )
        return [(record, metric) for record, metric in self._db.execute(stmt).all()]

    def get_record_fresh(self, record_id: int) -> CheckupRecord | None:
        stmt = (
            select(CheckupRecord)
            .where(CheckupRecord.id == record_id)
            .execution_options(populate_existing=True)
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def _lock_record(self, record_id: int) -> CheckupRecord:
        stmt = select(CheckupRecord).where(CheckupRecord.id == record_id).with_for_update()
        record = self._db.execute(stmt).scalar_one_or_none()
        if record is None:
            raise ValueError(f"Record not found: {record_id}")
        return record

    def lock_record(self, record_id: int) -> CheckupRecord:
        """수동 수정/검수 경로가 OCR upsert와 같은 락 경계를 공유하도록 노출한다."""
        return self._lock_record(record_id)

    def set_ocr_status(self, record: CheckupRecord, status: str) -> None:
        record.ocr_status = status
        self._db.flush()

    def set_verified(self, record: CheckupRecord) -> None:
        record.verification_status = VerificationStatus.VERIFIED.value
        record.verified_at = _now()
        self._db.flush()

    def list_metrics(self, record_id: int) -> list[CheckupMetricResult]:
        stmt = select(CheckupMetricResult).where(CheckupMetricResult.record_id == record_id)
        return list(self._db.execute(stmt).scalars().all())

    def get_metric(self, record_id: int, metric_id: int) -> CheckupMetricResult | None:
        metric = self._db.get(CheckupMetricResult, metric_id)
        if metric is None or metric.record_id != record_id:
            return None
        return metric

    def upsert_ocr_metrics(self, record_id: int, parsed: list[ParsedMetric]) -> int:
        self._lock_record(record_id)
        existing = self.list_metrics(record_id)
        manual_codes = {
            metric.metric_code
            for metric in existing
            if metric.is_edited or metric.source == MetricSource.MANUAL.value
        }
        for metric in existing:
            if not metric.is_edited and metric.source == MetricSource.OCR.value:
                self._db.delete(metric)
        self._db.flush()

        inserted = 0
        for parsed_metric in parsed:
            if parsed_metric.metric_code in manual_codes:
                continue
            self._db.add(
                CheckupMetricResult(
                    record_id=record_id,
                    metric_code=parsed_metric.metric_code,
                    metric_name=parsed_metric.metric_name,
                    value=parsed_metric.value,
                    unit=parsed_metric.unit,
                    source=MetricSource.OCR.value,
                    confidence=parsed_metric.confidence,
                    raw_text=parsed_metric.raw_text,
                    page_index=parsed_metric.page_index,
                    is_edited=False,
                )
            )
            inserted += 1
        self._db.flush()
        return inserted

    def insert_committed_metrics(
        self,
        record_id: int,
        metrics: list[CheckupMetricResult],
    ) -> int:
        self._lock_record(record_id)
        for metric in metrics:
            metric.record_id = record_id
            self._db.add(metric)
        self._db.flush()
        return len(metrics)

    def update_metric_value(
        self, metric: CheckupMetricResult, value: str, unit: str | None
    ) -> None:
        metric.value = value
        if unit is not None:
            metric.unit = unit
        metric.source = MetricSource.MANUAL.value
        metric.is_edited = True
        metric.confidence = None
        self._db.flush()

    def delete_record_cascade(self, record: CheckupRecord) -> list[str]:
        record = self._lock_record(record.id)
        file_urls: list[str] = []
        if record.file_url:
            file_urls.append(record.file_url)

        jobs = self._db.execute(select(OcrJob).where(OcrJob.record_id == record.id)).scalars().all()
        for job in jobs:
            self._db.delete(job)

        for metric in self.list_metrics(record.id):
            self._db.delete(metric)
        self._db.delete(record)
        self._db.flush()
        return file_urls
