from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.domains.ocr.status import OcrStatus
from app.domains.record.models import CheckupMetricResult, CheckupRecord
from app.domains.record.repository import RecordRepository
from app.domains.record.schemas import MetricUpdateItem
from app.infrastructure.storage.file_storage import FileStorage


class RecordService:
    def __init__(self, record_repo: RecordRepository, file_storage: FileStorage) -> None:
        self._record_repo = record_repo
        self._file_storage = file_storage

    def _get_owned_record(self, user_id: int, record_id: int) -> CheckupRecord:
        record = self._record_repo.get_record(record_id)
        if record is None:
            raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
        if record.user_id != user_id:
            raise ForbiddenException(message="해당 기록에 대한 권한이 없습니다.")
        return record

    def get_metrics(self, user_id: int, record_id: int) -> list[CheckupMetricResult]:
        self._get_owned_record(user_id, record_id)
        return self._record_repo.list_metrics(record_id)

    def _apply_metric_updates(
        self, record_id: int, items: list[MetricUpdateItem]
    ) -> None:
        """락 획득 → 전체 존재 검증 → 일괄 갱신(커밋은 호출자가 담당)."""
        # OCR upsert와 동일한 record 락 경계로 직렬화해 수정값 유실을 막는다.
        self._record_repo.lock_record(record_id)
        # 부분 반영 방지: 먼저 모든 대상의 존재를 검증한 뒤 일괄 갱신한다.
        pairs = []
        for item in items:
            metric = self._record_repo.get_metric(record_id, item.metric_id)
            if metric is None:
                raise NotFoundException(
                    message=f"수치(id={item.metric_id})를 찾을 수 없습니다."
                )
            pairs.append((metric, item))
        for metric, item in pairs:
            self._record_repo.update_metric_value(metric, item.value, item.unit)

    def update_metric(
        self, user_id: int, record_id: int, metric_id: int, value: str, unit: str | None
    ) -> CheckupMetricResult:
        self._get_owned_record(user_id, record_id)
        # OCR upsert와 동일한 record 락 경계로 직렬화해 수정값 유실을 막는다.
        self._record_repo.lock_record(record_id)
        metric = self._record_repo.get_metric(record_id, metric_id)
        if metric is None:
            raise NotFoundException(message="해당 수치를 찾을 수 없습니다.")
        self._record_repo.update_metric_value(metric, value, unit)
        self._record_repo.commit()
        return metric

    def bulk_update_metrics(
        self, user_id: int, record_id: int, items: list[MetricUpdateItem]
    ) -> list[CheckupMetricResult]:
        self._get_owned_record(user_id, record_id)
        self._apply_metric_updates(record_id, items)
        self._record_repo.commit()
        return self._record_repo.list_metrics(record_id)

    def verify(
        self, user_id: int, record_id: int, items: list[MetricUpdateItem] | None
    ) -> CheckupRecord:
        record = self._get_owned_record(user_id, record_id)
        if record.ocr_status != OcrStatus.COMPLETED.value:
            raise ConflictException(
                message="OCR 처리가 완료되지 않은 기록은 검수할 수 없습니다.",
                error_code="OCR_NOT_COMPLETED",
            )
        # 수치 수정과 검수 확정을 단일 트랜잭션으로 묶어 원자적으로 커밋한다.
        if items:
            self._apply_metric_updates(record_id, items)
        self._record_repo.set_verified(record)
        self._record_repo.commit()
        return record

    def delete_checkup(self, user_id: int, record_id: int) -> list[str]:
        """검진 기록과 연관 행을 삭제하고, 정리해야 할 파일 URL을 반환합니다.

        실제 스토리지 삭제는 DB 커밋이 성공한 뒤 purge_files()로 수행해야 한다.
        비가역 외부 삭제를 커밋 전에 실행하면 커밋 실패 시 DB는 복구되지만
        파일은 사라져 정합성이 깨진다.
        """
        record = self._get_owned_record(user_id, record_id)
        file_urls = self._record_repo.delete_record_cascade(record)
        # 파일 정리(purge_files)는 커밋 확정 이후에 호출자가 수행한다.
        self._record_repo.commit()
        return file_urls

    async def purge_files(self, file_urls: list[str]) -> None:
        for url in file_urls:
            try:
                await self._file_storage.delete(url)
            except Exception:  # noqa: BLE001 — best-effort 정리
                pass

    def upload_checkup(self, user_id: int, file, request) -> None:
        """검진 결과지를 업로드하고 분석 Job을 생성합니다.

        흐름:
        1. FileStorage에 결과지 저장
        2. CheckupRecord 생성
        3. AnalysisService.create_analysis_job() 호출
        4. MissionService.check_record_related_mission() (Phase 4)
        5. CharacterService.gain_exp() (Phase 4)
        """
        raise NotImplementedError

    def list_checkups(self, user_id: int):
        raise NotImplementedError

    def get_checkup(self, user_id: int, record_id: int):
        raise NotImplementedError

    def create_meal_record(self, user_id: int, request) -> None:
        raise NotImplementedError

    def list_meal_records(self, user_id: int):
        raise NotImplementedError
