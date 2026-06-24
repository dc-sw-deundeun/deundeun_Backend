import logging
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
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


@dataclass(frozen=True)
class UploadResult:
    record_id: int
    # 새로 생성된 잡 id. 중복 업로드(멱등)면 None이며 백그라운드 트리거를 건너뛴다.
    job_id: int | None
    is_duplicate: bool


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

    async def _safe_delete(self, file_url: str) -> None:
        """업로드된 파일을 best-effort로 정리한다(보상 삭제)."""
        try:
            await self._file_storage.delete(file_url)
        except Exception:  # noqa: BLE001
            pass

    async def upload_checkup(
        self, user_id: int, content: bytes, image_format: str, file_hash: str
    ) -> UploadResult:
        """결과지 업로드 트랜잭션 전체(중복 판정·저장·레코드/잡 생성·보상)를 담당한다."""
        existing = self._record_repo.find_by_user_and_hash(user_id, file_hash)
        if existing is not None:
            return UploadResult(record_id=existing.id, job_id=None, is_duplicate=True)

        key = f"checkups/{user_id}/{file_hash}.{image_format}"
        file_url = await self._file_storage.upload(key, content)
        try:
            record = self._record_repo.create_record(user_id, "UPLOAD", file_url, file_hash)
            job = await self.create_job(record.id, user_id)
            self._ocr_repo.commit()
        except IntegrityError:
            self._ocr_repo.rollback()
            existing = self._record_repo.find_by_user_and_hash(user_id, file_hash)
            if existing is None:
                # dedup 제약이 아닌 다른 무결성 위반. 고아 파일을 정리하고 전파한다.
                await self._safe_delete(file_url)
                raise
            # 중복 업로드: file_hash가 같아 경로가 동일(멱등)하므로 파일은 보존한다.
            return UploadResult(record_id=existing.id, job_id=None, is_duplicate=True)
        except Exception:
            # 커밋 실패 등으로 record가 남지 않는 경우 업로드된 파일을 정리한다.
            self._ocr_repo.rollback()
            await self._safe_delete(file_url)
            raise
        return UploadResult(record_id=record.id, job_id=job.id, is_duplicate=False)

    async def reprocess(self, user_id: int, record_id: int) -> OcrJob:
        """기존 기록의 원본 이미지로 OCR을 재요청한다."""
        record = self._record_repo.get_record(record_id)
        if record is None:
            raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
        if record.user_id != user_id:
            raise ForbiddenException(message="해당 기록에 대한 권한이 없습니다.")
        if not record.file_url or not await self._file_storage.exists(record.file_url):
            # OCR 성공 시 원본을 삭제하므로(프라이버시/스토리지) 완료된 레코드는
            # 재처리 대상이 아니다. reprocess는 사실상 '실패 잡 재시도' 용도다.
            if record.ocr_status == OcrStatus.COMPLETED.value:
                raise ConflictException(
                    message="이미 처리 완료되어 원본 이미지가 삭제되었습니다. 수치를 직접 수정해 주세요.",
                    error_code="IMAGE_UNAVAILABLE",
                )
            raise ConflictException(
                message="원본 이미지가 없어 재처리할 수 없습니다.",
                error_code="IMAGE_UNAVAILABLE",
            )
        self._record_repo.reset_verification(record)
        self._record_repo.set_ocr_status(record, OcrStatus.PENDING.value)
        job = await self.create_job(record_id, user_id)
        self._ocr_repo.commit()
        return job

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
            image_format = detect_image_format(image)
            if image_format is None:
                # 미지원/손상 이미지는 재시도 대상이 아니므로 즉시 실패 처리한다.
                self._mark_processing_failure(
                    job, "unsupported_image_format", ValueError("unsupported_image_format")
                )
                return
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
        # 주의: 이로 인해 COMPLETED 레코드는 reprocess가 불가하다(설계상 의도).
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
