from app.core.exceptions import ConflictException, NotFoundException
from app.domains.ocr.status import VerificationStatus
from app.domains.record.repository import RecordRepository


class AnalysisService:
    def __init__(self, record_repo: RecordRepository | None = None) -> None:
        self._record_repo = record_repo

    def ensure_verified(self, record_id: int) -> None:
        if self._record_repo is None:
            raise RuntimeError("AnalysisService에 record_repo가 주입되지 않았습니다.")
        record = self._record_repo.get_record(record_id)
        if record is None:
            raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
        if record.verification_status != VerificationStatus.VERIFIED.value:
            raise ConflictException(
                message="검수가 완료되지 않은 기록은 분석할 수 없습니다.",
                error_code="NOT_VERIFIED",
            )

    def create_analysis_job(self, record_id: int, user_id: int):
        raise NotImplementedError

    def get_job_status(self, job_id: int):
        raise NotImplementedError

    def get_job_result(self, job_id: int):
        raise NotImplementedError

    def handle_callback(self, payload) -> None:
        raise NotImplementedError

    def poll_pending_jobs(self) -> None:
        raise NotImplementedError
