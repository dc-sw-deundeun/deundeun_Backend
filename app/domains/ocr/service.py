import logging

from app.domains.ocr.models import OcrJob
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.status import OcrStatus
from app.domains.record.repository import RecordRepository
from app.infrastructure.ocr.format import detect_image_format
from app.infrastructure.ocr.ocr_client import OcrClient
from app.infrastructure.ocr.ocr_dto import OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser
from app.infrastructure.storage.file_storage import FileStorage

logger = logging.getLogger(__name__)


class OcrService:
    def __init__(
        self,
        ocr_repo: OcrRepository,
        record_repo: RecordRepository,
        ocr_client: OcrClient,
        file_storage: FileStorage,
        parser: OcrParser,
        *,
        max_retries: int = 2,
    ) -> None:
        self._ocr_repo = ocr_repo
        self._record_repo = record_repo
        self._ocr_client = ocr_client
        self._file_storage = file_storage
        self._parser = parser
        self._max_retries = max_retries

    async def create_job(self, record_id: int, user_id: int) -> OcrJob:
        return self._ocr_repo.create_job(record_id=record_id, user_id=user_id)

    def get_job(self, job_id: int) -> OcrJob | None:
        return self._ocr_repo.get_job(job_id)

    async def process_pending(self) -> int:
        processed = 0
        while True:
            job = self._ocr_repo.claim_next_pending()
            if job is None:
                self._ocr_repo.rollback()
                break
            job_id = job.id
            self._ocr_repo.commit()
            try:
                await self.process_job(job)
                self._ocr_repo.commit()
            except Exception as exc:  # noqa: BLE001
                self._ocr_repo.rollback()
                logger.warning(
                    "ocr_batch_job_unhandled_failure",
                    extra={"job_id": job_id, "error_type": type(exc).__name__},
                )
            processed += 1
        return processed

    async def process_job(self, job: OcrJob) -> None:
        record = self._record_repo.get_record_fresh(job.record_id)
        if record is None:
            self._mark_deleted_record_failure(job, "record_missing")
            return

        try:
            image = await self._file_storage.read(record.file_url)
            image_format = detect_image_format(image) or "png"
            result = await self._recognize_with_retry(image, image_format)
        except Exception as exc:  # noqa: BLE001
            self._mark_processing_failure(job, "recognize_failed", exc)
            return

        record = self._record_repo.get_record_fresh(job.record_id)
        if record is None:
            self._mark_deleted_record_failure(job, "record_deleted")
            return

        try:
            with self._ocr_repo.begin_nested():
                parsed = self._parser.parse(result)
                parsed_count = self._record_repo.upsert_ocr_metrics(job.record_id, parsed)
                self._ocr_repo.mark_completed(job, parsed_count)
                self._record_repo.set_ocr_status(record, OcrStatus.COMPLETED.value)
            self._ocr_repo.commit()
        except ValueError:
            self._mark_deleted_record_failure(job, "record_deleted_during_upsert")
            return
        except Exception as exc:  # noqa: BLE001
            self._ocr_repo.rollback()
            self._mark_processing_failure(job, "processing_failed", exc)
            return
        # 커밋 성공 이후에만 원본 이미지를 best-effort 삭제한다.
        try:
            await self._file_storage.delete(record.file_url)
        except Exception:  # noqa: BLE001
            pass
        logger.info("ocr_job_completed", extra={"job_id": job.id, "parsed_field_count": parsed_count})

    async def _recognize_with_retry(self, image: bytes, image_format: str) -> OcrResultDTO:
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                return await self._ocr_client.recognize(image, image_format)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if last_error is None:
            raise RuntimeError("OCR recognition was not attempted")
        raise last_error

    async def process_single(self, job_id: int) -> None:
        job = self._ocr_repo.claim_job(job_id)
        if job is None:
            self._ocr_repo.rollback()
            return
        self._ocr_repo.commit()
        try:
            await self.process_job(job)
            self._ocr_repo.commit()
        except Exception as exc:  # noqa: BLE001
            self._ocr_repo.rollback()
            logger.warning(
                "ocr_single_job_unhandled_failure",
                extra={"job_id": job_id, "error_type": type(exc).__name__},
            )

    def _mark_processing_failure(
        self,
        job: OcrJob,
        event: str,
        error: Exception,
    ) -> None:
        current_job = self._ocr_repo.get_job_fresh(job.id)
        current_record = self._record_repo.get_record_fresh(job.record_id)
        if current_job is not None:
            self._ocr_repo.mark_failed(current_job, event)
        if current_record is not None:
            self._record_repo.set_ocr_status(current_record, OcrStatus.FAILED.value)
        logger.warning(
            event,
            extra={"job_id": job.id, "error_type": type(error).__name__},
        )

    def _mark_deleted_record_failure(self, job: OcrJob, event: str) -> None:
        current_job = self._ocr_repo.get_job_fresh(job.id)
        if current_job is not None:
            self._ocr_repo.mark_failed(current_job, event)
        logger.warning(event, extra={"job_id": job.id})
