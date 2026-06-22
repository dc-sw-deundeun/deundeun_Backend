import time
import uuid

import httpx

from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO


class ClovaOcrClient:
    """Naver Clova OCR General 모드 클라이언트입니다."""

    def __init__(
        self,
        invoke_url: str,
        secret_key: str,
        timeout: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._invoke_url = invoke_url
        self._secret_key = secret_key
        self._timeout = timeout
        self._http_client = http_client

    async def recognize(self, file_url: str) -> OcrResultDTO:
        payload = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "images": [{"format": "png", "name": "checkup", "url": file_url}],
        }
        headers = {"X-OCR-SECRET": self._secret_key}

        if self._http_client is not None:
            response = await self._http_client.post(
                self._invoke_url, json=payload, headers=headers, timeout=self._timeout
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                response = await http.post(
                    self._invoke_url, json=payload, headers=headers
                )
        response.raise_for_status()
        return self._to_dto(response.json())

    def _to_dto(self, body: dict) -> OcrResultDTO:
        fields: list[OcrFieldDTO] = []
        images = body.get("images") or []
        for image in images:
            for raw in image.get("fields") or []:
                vertices = (raw.get("boundingPoly") or {}).get("vertices")
                if not vertices:
                    continue
                fields.append(
                    OcrFieldDTO.from_vertices(
                        text=raw.get("inferText", ""),
                        confidence=raw.get("inferConfidence", 0.0),
                        vertices=vertices,
                    )
                )
        return OcrResultDTO(fields=fields)
