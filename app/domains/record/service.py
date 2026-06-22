from app.core.exceptions import ForbiddenException, NotFoundException
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

    def update_metric(
        self, user_id: int, record_id: int, metric_id: int, value: str, unit: str | None
    ) -> CheckupMetricResult:
        self._get_owned_record(user_id, record_id)
        metric = self._record_repo.get_metric(record_id, metric_id)
        if metric is None:
            raise NotFoundException(message="해당 수치를 찾을 수 없습니다.")
        self._record_repo.update_metric_value(metric, value, unit)
        return metric

    def bulk_update_metrics(
        self, user_id: int, record_id: int, items: list[MetricUpdateItem]
    ) -> list[CheckupMetricResult]:
        self._get_owned_record(user_id, record_id)
        for item in items:
            metric = self._record_repo.get_metric(record_id, item.metric_id)
            if metric is None:
                raise NotFoundException(
                    message=f"수치(id={item.metric_id})를 찾을 수 없습니다."
                )
            self._record_repo.update_metric_value(metric, item.value, item.unit)
        return self._record_repo.list_metrics(record_id)

    def verify(
        self, user_id: int, record_id: int, items: list[MetricUpdateItem] | None
    ) -> CheckupRecord:
        record = self._get_owned_record(user_id, record_id)
        if items:
            self.bulk_update_metrics(user_id, record_id, items)
        self._record_repo.set_verified(record)
        return record

    async def delete_checkup(self, user_id: int, record_id: int) -> None:
        record = self._get_owned_record(user_id, record_id)
        file_urls = self._record_repo.delete_record_cascade(record)
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
