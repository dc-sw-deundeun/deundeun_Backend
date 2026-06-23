from typing import Protocol

from app.infrastructure.ocr.ocr_dto import OcrResultDTO


class OcrClient(Protocol):
    """OCR 엔진 호출 인터페이스입니다. Clova → 타 엔진으로 교체 가능합니다."""

    async def recognize(self, image: bytes, image_format: str) -> OcrResultDTO: ...


class StubOcrClient:
    """개발/테스트용 stub 구현입니다."""

    async def recognize(self, image: bytes, image_format: str) -> OcrResultDTO:
        raise NotImplementedError
