import json
import logging

from sqlalchemy.orm import object_session

from app.domains.ocr.models import OcrJob
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.status import OcrStatus
from app.domains.record.models import CheckupRecord
from app.domains.record.repository import RecordRepository
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
        while job := self._ocr_repo.claim_next_pending():
            await self.process_job(job)
            processed += 1
        return processed

    async def process_job(self, job: OcrJob) -> None:
        record = self._record_repo.get_record(job.record_id)
        if record is None:
            self._mark_deleted_record_failure(job, "record_missing")
            return

        try:
            result = await self._recognize_with_retry(record.file_url)
        except Exception as exc:  # noqa: BLE001
            self._mark_processing_failure(job, record, "recognize_failed", exc)
            return

        record = self._record_repo.get_record(job.record_id)
        if record is None:
            self._mark_deleted_record_failure(job, "record_deleted")
            return

        raw_result_url = await self._store_raw(job, result)
        try:
            session = object_session(job)
            if session is None:
                raise RuntimeError("OCR job is detached from its session")
            with session.begin_nested():
                parsed = self._parser.parse(result)
                parsed_count = self._record_repo.upsert_ocr_metrics(job.record_id, parsed)
                self._ocr_repo.mark_completed(
                    job,
                    raw_result_url=raw_result_url,
                    parsed_field_count=parsed_count,
                )
                self._record_repo.set_ocr_status(record, OcrStatus.COMPLETED.value)
        except ValueError:
            self._mark_deleted_record_failure(job, "record_deleted_during_upsert")
            return
        except Exception as exc:  # noqa: BLE001
            self._mark_processing_failure(job, record, "processing_failed", exc)
            return

        logger.info(
            "ocr_job_completed",
            extra={"job_id": job.id, "parsed_field_count": parsed_count},
        )

    async def _recognize_with_retry(self, file_url: str) -> OcrResultDTO:
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                return await self._ocr_client.recognize(file_url)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if last_error is None:
            raise RuntimeError("OCR recognition was not attempted")
        raise last_error

    async def _store_raw(self, job: OcrJob, result: OcrResultDTO) -> str | None:
        try:
            content = json.dumps(result.model_dump(), ensure_ascii=False).encode("utf-8")
            return await self._file_storage.upload(f"ocr/raw/{job.id}.json", content)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ocr_raw_storage_failed",
                extra={"job_id": job.id, "error_type": type(exc).__name__},
            )
            return None

    def _mark_processing_failure(
        self,
        job: OcrJob,
        record: CheckupRecord,
        event: str,
        error: Exception,
    ) -> None:
        self._ocr_repo.mark_failed(job, event)
        self._record_repo.set_ocr_status(record, OcrStatus.FAILED.value)
        logger.warning(
            event,
            extra={"job_id": job.id, "error_type": type(error).__name__},
        )

    def _mark_deleted_record_failure(self, job: OcrJob, event: str) -> None:
        self._ocr_repo.mark_failed(job, event)
        logger.warning(event, extra={"job_id": job.id})
