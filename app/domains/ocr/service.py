import asyncio
import logging
from dataclasses import dataclass

import httpx

from app.core.exceptions import OcrBusyException, OcrFailedException
from app.domains.ocr.models import OcrJob
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.status import MetricSource, OcrStatus, VerificationStatus
from app.domains.record.models import CheckupMetricResult
from app.domains.record.repository import RecordRepository
from app.infrastructure.ocr.format import detect_image_format
from app.infrastructure.ocr.ocr_client import OcrClient
from app.infrastructure.ocr.ocr_dto import OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser, ParsedMetric

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadOutcome:
    page_count: int
    failed_pages: list[int]
    metrics: list[ParsedMetric]
    ocr_status: str


@dataclass(frozen=True)
class FinalMetric:
    metric_code: str
    metric_name: str
    value: str | None
    unit: str | None
    confidence: float | None
    raw_text: str | None
    page_index: int | None
    is_edited: bool = False


@dataclass(frozen=True)
class CommitOutcome:
    record_id: int
    metrics: list[CheckupMetricResult]
    verification_status: str


class OcrService:
    def __init__(
        self,
        ocr_repo: OcrRepository,
        record_repo: RecordRepository,
        ocr_client: OcrClient,
        parser: OcrParser,
        *,
        max_retries: int = 1,
        concurrency: int = 5,
        global_limiter: asyncio.Semaphore | None = None,
        acquire_timeout_seconds: float = 1.0,
        retry_after_seconds: int = 10,
    ) -> None:
        self._ocr_repo = ocr_repo
        self._record_repo = record_repo
        self._ocr_client = ocr_client
        self._parser = parser
        self._max_retries = max_retries
        self._concurrency = concurrency
        self._global_limiter = global_limiter
        self._acquire_timeout_seconds = acquire_timeout_seconds
        self._retry_after_seconds = retry_after_seconds

    def get_job(self, job_id: int) -> OcrJob | None:
        return self._ocr_repo.get_job(job_id)

    async def process_upload(self, user_id: int, images: list[bytes]) -> UploadOutcome:
        semaphore = asyncio.Semaphore(self._concurrency)
        pairs: list[tuple[int, OcrResultDTO | BaseException]] = list(
            await asyncio.gather(
                *[self._call_one(image, idx, semaphore) for idx, image in enumerate(images)]
            )
        )

        successful: list[tuple[int, OcrResultDTO]] = []
        failed_pages: list[int] = []
        for idx, result in pairs:
            if isinstance(result, OcrBusyException):
                raise result
            if isinstance(result, BaseException):
                failed_pages.append(idx)
                logger.warning(
                    "ocr_page_failed",
                    extra={"page_index": idx, "error_type": type(result).__name__},
                )
            else:
                successful.append((idx, result))

        if not successful:
            raise OcrFailedException()

        parsed: list[ParsedMetric] = []
        for idx, result in successful:
            for metric in self._parser.parse(result):
                parsed.append(
                    ParsedMetric(
                        metric_code=metric.metric_code,
                        metric_name=metric.metric_name,
                        value=metric.value,
                        unit=metric.unit,
                        confidence=metric.confidence,
                        raw_text=metric.raw_text,
                        page_index=idx,
                        out_of_range=metric.out_of_range,
                    )
                )

        merged = self._merge_metrics(parsed)
        ocr_status = OcrStatus.PARTIAL.value if failed_pages else OcrStatus.COMPLETED.value

        logger.info(
            "ocr_preview_completed",
            extra={
                "user_id": user_id,
                "page_count": len(images),
                "failed_pages": failed_pages,
                "parsed_count": len(merged),
            },
        )
        return UploadOutcome(
            page_count=len(images),
            failed_pages=failed_pages,
            metrics=merged,
            ocr_status=ocr_status,
        )

    def commit_upload(
        self,
        user_id: int,
        *,
        ocr_status: str,
        failed_pages: list[int],
        metrics: list[FinalMetric],
    ) -> CommitOutcome:
        try:
            record = self._record_repo.create_record(user_id, "UPLOAD", ocr_status=ocr_status)
            rows = [
                CheckupMetricResult(
                    record_id=record.id,
                    metric_code=metric.metric_code,
                    metric_name=metric.metric_name,
                    value=metric.value,
                    unit=metric.unit,
                    source=MetricSource.MANUAL.value
                    if metric.is_edited
                    else MetricSource.OCR.value,
                    confidence=metric.confidence,
                    raw_text=metric.raw_text,
                    page_index=metric.page_index,
                    is_edited=metric.is_edited,
                )
                for metric in metrics
            ]
            parsed_count = self._record_repo.insert_committed_metrics(record.id, rows)
            error_message = f"pages {sorted(failed_pages)} failed" if failed_pages else None
            self._ocr_repo.create_job(
                record.id,
                user_id,
                status=ocr_status,
                parsed_field_count=parsed_count,
                error_message=error_message,
            )
            self._record_repo.set_verified(record)
            self._ocr_repo.commit()
        except Exception:
            self._ocr_repo.rollback()
            raise

        persisted_metrics = self._record_repo.list_metrics(record.id)
        logger.info(
            "ocr_upload_committed",
            extra={
                "user_id": user_id,
                "record_id": record.id,
                "failed_pages": failed_pages,
                "parsed_count": parsed_count,
            },
        )
        return CommitOutcome(
            record_id=record.id,
            metrics=persisted_metrics,
            verification_status=record.verification_status or VerificationStatus.VERIFIED.value,
        )

    async def _call_one(
        self, image: bytes, idx: int, semaphore: asyncio.Semaphore
    ) -> tuple[int, OcrResultDTO | BaseException]:
        async with semaphore:
            try:
                image_format = detect_image_format(image) or "jpg"
                result = await self._recognize_with_retry(image, image_format)
                return idx, result
            except Exception as exc:  # noqa: BLE001
                return idx, exc

    def _merge_metrics(self, parsed: list[ParsedMetric]) -> list[ParsedMetric]:
        best: dict[str, ParsedMetric] = {}
        for metric in parsed:
            existing = best.get(metric.metric_code)
            if existing is None or metric.confidence > existing.confidence:
                best[metric.metric_code] = metric
        return list(best.values())

    async def _recognize_with_retry(self, image: bytes, image_format: str) -> OcrResultDTO:
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                return await self._recognize_with_capacity(image, image_format)
            except OcrBusyException:
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code < 500:
                    raise  # 4xx: permanent client error, do not retry
                last_error = exc
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if last_error is None:
            raise RuntimeError("OCR recognition was not attempted")
        raise last_error

    async def _recognize_with_capacity(self, image: bytes, image_format: str) -> OcrResultDTO:
        if self._global_limiter is None:
            return await self._ocr_client.recognize(image, image_format)

        acquired = False
        try:
            await asyncio.wait_for(
                self._global_limiter.acquire(),
                timeout=self._acquire_timeout_seconds,
            )
            acquired = True
            return await self._ocr_client.recognize(image, image_format)
        except TimeoutError as exc:
            raise OcrBusyException(retry_after_seconds=self._retry_after_seconds) from exc
        finally:
            if acquired:
                self._global_limiter.release()
