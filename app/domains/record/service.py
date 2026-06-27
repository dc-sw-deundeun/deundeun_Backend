from datetime import datetime

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.domains.health_metric.metric_evaluator import evaluate_metric_status
from app.domains.health_metric.repository import HealthMetricRepository
from app.domains.onboarding.hooks import advance_to_checkup_verified
from app.domains.onboarding.repository import OnboardingRepository
from app.domains.ocr.status import MetricSource, OcrStatus
from app.domains.record.models import CheckupMetricResult, CheckupRecord
from app.domains.record.repository import RecordRepository
from app.domains.record.schemas import (
    CheckupDetailResponse,
    CheckupListItem,
    CheckupListResponse,
    CheckupTrendsResponse,
    CommitMetricRequest,
    ManualCheckupRequest,
    MetricResponse,
    MetricTrendSeries,
    MetricUpdateItem,
    TrendPoint,
)


_OVERALL_PRIORITY = {"RISK": 3, "CAUTION": 2, "UNKNOWN": 1, "NORMAL": 0}


class RecordService:
    def __init__(
        self,
        record_repo: RecordRepository,
        onboarding_repo: OnboardingRepository | None = None,
        health_metric_repo: HealthMetricRepository | None = None,
    ) -> None:
        self._record_repo = record_repo
        self._onboarding_repo = onboarding_repo
        self._health_metric_repo = health_metric_repo or HealthMetricRepository(record_repo._db)

    def _get_owned_record(self, user_id: int, record_id: int) -> CheckupRecord:
        record = self._record_repo.get_record(record_id)
        if record is None:
            raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
        if record.user_id != user_id:
            raise ForbiddenException(message="해당 기록에 대한 권한이 없습니다.")
        return record

    def _apply_metric_evaluation(self, metric: CheckupMetricResult) -> None:
        metric.status = evaluate_metric_status(metric.metric_code, metric.value)
        reference = self._health_metric_repo.find_by_metric_code(metric.metric_code)
        metric.reference_min = reference.reference_min if reference else None
        metric.reference_max = reference.reference_max if reference else None

    def _freeze_metric_evaluations(self, record_id: int) -> None:
        for metric in self._record_repo.list_metrics(record_id):
            self._apply_metric_evaluation(metric)

    def _enrich_metric(self, metric: CheckupMetricResult) -> MetricResponse:
        if metric.status is not None:
            return MetricResponse.from_model(
                metric,
                min_confidence=0.8,
                reference_min=metric.reference_min,
                reference_max=metric.reference_max,
                status=metric.status,
            )
        reference = self._health_metric_repo.find_by_metric_code(metric.metric_code)
        status = evaluate_metric_status(metric.metric_code, metric.value)
        return MetricResponse.from_model(
            metric,
            min_confidence=0.8,
            reference_min=reference.reference_min if reference else None,
            reference_max=reference.reference_max if reference else None,
            status=status,
        )

    def _overall_status(self, metrics: list[MetricResponse]) -> str:
        statuses = [m.status for m in metrics if m.status]
        if not statuses:
            return "UNKNOWN"
        return max(statuses, key=lambda s: _OVERALL_PRIORITY.get(s, 0))

    def get_metrics(self, user_id: int, record_id: int) -> list[MetricResponse]:
        self._get_owned_record(user_id, record_id)
        return [self._enrich_metric(m) for m in self._record_repo.list_metrics(record_id)]

    def _apply_metric_updates(self, record_id: int, items: list[MetricUpdateItem]) -> None:
        self._record_repo.lock_record(record_id)
        pairs = []
        for item in items:
            metric = self._record_repo.get_metric(record_id, item.metric_id)
            if metric is None:
                raise NotFoundException(message=f"수치(id={item.metric_id})를 찾을 수 없습니다.")
            pairs.append((metric, item))
        for metric, item in pairs:
            self._record_repo.update_metric_value(metric, item.value, item.unit)
            self._apply_metric_evaluation(metric)

    def update_metric(
        self, user_id: int, record_id: int, metric_id: int, value: str, unit: str | None
    ) -> MetricResponse:
        self._get_owned_record(user_id, record_id)
        self._record_repo.lock_record(record_id)
        metric = self._record_repo.get_metric(record_id, metric_id)
        if metric is None:
            raise NotFoundException(message="해당 수치를 찾을 수 없습니다.")
        self._record_repo.update_metric_value(metric, value, unit)
        self._apply_metric_evaluation(metric)
        self._record_repo.commit()
        return self._enrich_metric(metric)

    def bulk_update_metrics(
        self, user_id: int, record_id: int, items: list[MetricUpdateItem]
    ) -> list[MetricResponse]:
        self._get_owned_record(user_id, record_id)
        self._apply_metric_updates(record_id, items)
        self._record_repo.commit()
        return self.get_metrics(user_id, record_id)

    def verify(
        self, user_id: int, record_id: int, items: list[MetricUpdateItem] | None
    ) -> CheckupRecord:
        record = self._get_owned_record(user_id, record_id)
        if record.ocr_status not in {OcrStatus.COMPLETED.value, OcrStatus.PARTIAL.value}:
            raise ConflictException(
                message="OCR 처리가 완료되지 않은 기록은 검수할 수 없습니다.",
                error_code="OCR_NOT_COMPLETED",
            )
        if items:
            self._apply_metric_updates(record_id, items)
        self._freeze_metric_evaluations(record_id)
        self._record_repo.set_verified(record)
        if self._onboarding_repo is not None:
            user = self._onboarding_repo.get_user_by_id(user_id)
            if user is not None:
                advance_to_checkup_verified(user)
        self._record_repo.commit()
        return record

    def delete_checkup(self, user_id: int, record_id: int) -> None:
        record = self._get_owned_record(user_id, record_id)
        self._record_repo.delete_record_cascade(record)
        self._record_repo.commit()

    def list_checkups(self, user_id: int, *, page: int = 1, size: int = 20) -> CheckupListResponse:
        if page < 1:
            page = 1
        if size < 1:
            size = 20
        offset = (page - 1) * size
        records, total = self._record_repo.list_checkups_by_user(user_id, offset=offset, limit=size)
        items = [
            CheckupListItem(
                record_id=record.id,
                source_type=record.source_type,
                verification_status=record.verification_status,
                analysis_status=record.analysis_status,
                ocr_status=record.ocr_status,
                measured_at=record.measured_at,
                created_at=record.created_at,
                metric_count=self._record_repo.count_metrics(record.id),
            )
            for record in records
        ]
        return CheckupListResponse(items=items, page=page, size=size, total=total)

    def get_checkup(self, user_id: int, record_id: int) -> CheckupDetailResponse:
        record = self._get_owned_record(user_id, record_id)
        metrics = self.get_metrics(user_id, record_id)
        return CheckupDetailResponse(
            record_id=record.id,
            source_type=record.source_type,
            verification_status=record.verification_status,
            analysis_status=record.analysis_status,
            ocr_status=record.ocr_status,
            measured_at=record.measured_at,
            verified_at=record.verified_at,
            created_at=record.created_at,
            overall_status=self._overall_status(metrics),
            metrics=metrics,
        )

    def create_manual(self, user_id: int, request: ManualCheckupRequest) -> CheckupRecord:
        record = self._record_repo.create_record(
            user_id,
            "MANUAL",
            ocr_status=OcrStatus.COMPLETED.value,
        )
        if request.measured_at is not None:
            record.measured_at = request.measured_at
        rows = self._build_metric_rows(record.id, request.metrics, source=MetricSource.MANUAL.value)
        self._record_repo.insert_committed_metrics(record.id, rows)
        self._record_repo.commit()
        return record

    def get_trends(self, user_id: int, record_id: int) -> CheckupTrendsResponse:
        record = self._get_owned_record(user_id, record_id)
        metrics = self._record_repo.list_metrics(record.id)
        metric_codes = sorted({m.metric_code for m in metrics})
        name_by_code = {m.metric_code: m.metric_name for m in metrics}
        series_rows = self._record_repo.list_trend_series(user_id, metric_codes)

        grouped: dict[str, list[TrendPoint]] = {code: [] for code in metric_codes}
        for rec, metric in series_rows:
            event_at = rec.measured_at or rec.created_at
            grouped[metric.metric_code].append(
                TrendPoint(
                    record_id=rec.id,
                    date=event_at.date().isoformat(),
                    value=metric.value or "",
                    unit=metric.unit,
                )
            )

        trends = [
            MetricTrendSeries(
                metric_code=code,
                metric_name=name_by_code.get(code, code),
                points=grouped[code],
            )
            for code in metric_codes
        ]
        return CheckupTrendsResponse(record_id=record.id, trends=trends)

    def _build_metric_rows(
        self,
        record_id: int,
        items: list[CommitMetricRequest],
        *,
        source: str,
    ) -> list[CheckupMetricResult]:
        rows: list[CheckupMetricResult] = []
        for item in items:
            reference = self._health_metric_repo.find_by_metric_code(item.metric_code)
            rows.append(
                CheckupMetricResult(
                    record_id=record_id,
                    metric_code=item.metric_code,
                    metric_name=item.metric_name,
                    value=item.value,
                    unit=item.unit,
                    source=source,
                    confidence=item.confidence,
                    raw_text=item.raw_text,
                    page_index=item.page_index,
                    is_edited=item.is_edited,
                    status=evaluate_metric_status(item.metric_code, item.value),
                    reference_min=reference.reference_min if reference else None,
                    reference_max=reference.reference_max if reference else None,
                )
            )
        return rows
