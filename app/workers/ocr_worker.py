import logging

from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService

logger = logging.getLogger(__name__)


def recover_stuck(ocr_repo: OcrRepository, stuck_timeout_seconds: int) -> int:
    stuck = ocr_repo.find_stuck_jobs(stuck_timeout_seconds)
    for job in stuck:
        ocr_repo.mark_failed(job, "stuck job recovered (timeout)")
        logger.warning("OCR job %s recovered from stuck state", job.id)
    return len(stuck)


async def run_ocr_batch(
    service: OcrService, ocr_repo: OcrRepository, stuck_timeout_seconds: int
) -> int:
    recover_stuck(ocr_repo, stuck_timeout_seconds)
    return await service.process_pending()
