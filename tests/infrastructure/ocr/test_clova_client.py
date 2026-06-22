import httpx
import pytest

from app.infrastructure.ocr.clova_client import ClovaOcrClient


def _clova_response():
    return {
        "images": [
            {
                "fields": [
                    {
                        "inferText": "공복혈당",
                        "inferConfidence": 0.98,
                        "boundingPoly": {
                            "vertices": [
                                {"x": 10, "y": 100}, {"x": 60, "y": 100},
                                {"x": 60, "y": 130}, {"x": 10, "y": 130},
                            ]
                        },
                    },
                    {
                        "inferText": "109",
                        "inferConfidence": 0.95,
                        "boundingPoly": {
                            "vertices": [
                                {"x": 120, "y": 100}, {"x": 160, "y": 100},
                                {"x": 160, "y": 130}, {"x": 120, "y": 130},
                            ]
                        },
                    },
                ]
            }
        ]
    }


@pytest.mark.asyncio
async def test_recognize_maps_response_to_dto():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["secret"] = request.headers.get("X-OCR-SECRET")
        return httpx.Response(200, json=_clova_response())

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = ClovaOcrClient(
            invoke_url="https://clova.test/ocr",
            secret_key="secret-123",
            http_client=http,
        )
        result = await client.recognize("https://files.test/checkup.png")

    assert captured["secret"] == "secret-123"
    texts = {f.text for f in result.fields}
    assert texts == {"공복혈당", "109"}
    glucose = next(f for f in result.fields if f.text == "109")
    assert glucose.confidence == 0.95
    assert glucose.x_min == 120


@pytest.mark.asyncio
async def test_recognize_raises_on_http_error():
    transport = httpx.MockTransport(lambda req: httpx.Response(500))
    async with httpx.AsyncClient(transport=transport) as http:
        client = ClovaOcrClient("https://clova.test/ocr", "s", http_client=http)
        with pytest.raises(httpx.HTTPStatusError):
            await client.recognize("https://files.test/checkup.png")


@pytest.mark.asyncio
async def test_recognize_skips_fields_without_bounding_poly():
    response_body = {
        "images": [
            {
                "fields": [
                    {
                        "inferText": "유효한필드",
                        "inferConfidence": 0.99,
                        "boundingPoly": {
                            "vertices": [
                                {"x": 10, "y": 100}, {"x": 60, "y": 100},
                                {"x": 60, "y": 130}, {"x": 10, "y": 130},
                            ]
                        },
                    },
                    {
                        "inferText": "boundingPoly없음",
                        "inferConfidence": 0.42,
                    },
                ]
            }
        ]
    }

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=response_body))
    async with httpx.AsyncClient(transport=transport) as http:
        client = ClovaOcrClient(
            invoke_url="https://clova.test/ocr",
            secret_key="secret-123",
            http_client=http,
        )
        result = await client.recognize("https://files.test/checkup.png")

    assert len(result.fields) == 1
    assert result.fields[0].text == "유효한필드"
    assert result.fields[0].confidence == 0.99
