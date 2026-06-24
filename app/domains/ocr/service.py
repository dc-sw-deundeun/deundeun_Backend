import asyncio
import logging
from dataclasses import dataclass

from app.core.exceptions import OcrFailedException
from app.domains.ocr.models import OcrJob
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.status import OcrStatus
from app.domains.record.models import CheckupMetricResult
from app.domains.record.repository import RecordRepository
from app.infrastructure.ocr.format import detect_image_format
from app.infrastructure.ocr.ocr_client import OcrClient
from app.infrastructure.ocr.ocr_dto import OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser, ParsedMetric

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadOutcome:
    record_id: int
    page_count: int
    failed_pages: list[int]
    metrics: list[CheckupMetricResult]
    ocr_status: str


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
    ) -> None:
        self._ocr_repo = ocr_repo
        self._record_repo = record_repo
        self._ocr_client = ocr_client
        self._parser = parser
        self._max_retries = max_retries
        self._concurrency = concurrency

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
                    )
                )

        merged = self._merge_metrics(parsed)
        ocr_status = OcrStatus.PARTIAL.value if failed_pages else OcrStatus.COMPLETED.value
        error_message = f"pages {sorted(failed_pages)} failed" if failed_pages else None

        record = self._record_repo.create_record(user_id, "UPLOAD", ocr_status=ocr_status)
        parsed_count = self._record_repo.upsert_ocr_metrics(record.id, merged)
        self._ocr_repo.create_job(
            record.id,
            user_id,
            status=ocr_status,
            parsed_field_count=parsed_count,
            error_message=error_message,
        )
        self._ocr_repo.commit()

        metrics = self._record_repo.list_metrics(record.id)
        logger.info(
            "ocr_upload_completed",
            extra={
                "user_id": user_id,
                "record_id": record.id,
                "page_count": len(images),
                "failed_pages": failed_pages,
                "parsed_count": parsed_count,
            },
        )
        return UploadOutcome(
            record_id=record.id,
            page_count=len(images),
            failed_pages=failed_pages,
            metrics=metrics,
            ocr_status=ocr_status,
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
                return await self._ocr_client.recognize(image, image_format)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if last_error is None:
            raise RuntimeError("OCR recognition was not attempted")
        raise last_error
