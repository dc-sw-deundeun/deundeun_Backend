import logging

from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.ocr.status import OcrStatus
from app.domains.record.repository import RecordRepository

logger = logging.getLogger(__name__)


def recover_stuck(
    ocr_repo: OcrRepository,
    record_repo: RecordRepository,
    stuck_timeout_seconds: int,
) -> int:
    stuck = ocr_repo.find_stuck_jobs(stuck_timeout_seconds)
    for job in stuck:
        ocr_repo.mark_failed(job, "stuck job recovered (timeout)")
        # Job과 Record 상태를 함께 FAILED로 전이해 정합성을 맞춘다.
        # (이미 삭제된 record는 None이므로 건너뛴다.)
        record = record_repo.get_record(job.record_id)
        if record is not None:
            record_repo.set_ocr_status(record, OcrStatus.FAILED.value)
        logger.warning("OCR job %s recovered from stuck state", job.id)
    # 회수 결과를 즉시 확정한다. 그렇지 않으면 pending 큐가 비어 있을 때
    # process_pending()의 rollback()이 stuck 회수까지 되돌린다.
    ocr_repo.commit()
    return len(stuck)


async def run_ocr_batch(
    service: OcrService,
    ocr_repo: OcrRepository,
    record_repo: RecordRepository,
    stuck_timeout_seconds: int,
) -> int:
    recover_stuck(ocr_repo, record_repo, stuck_timeout_seconds)
    return await service.process_pending()
