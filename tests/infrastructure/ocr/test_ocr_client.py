import pytest

from app.infrastructure.ocr.ocr_client import StubOcrClient


@pytest.mark.asyncio
async def test_stub_recognize_not_implemented():
    with pytest.raises(NotImplementedError):
        await StubOcrClient().recognize("https://example.com/a.png")
