from typing import Protocol


class WearableClient(Protocol):
    """웨어러블 디바이스 연동 인터페이스입니다."""

    async def connect(self, user_id: int, device_token: str) -> None: ...

    async def fetch_health_data(self, user_id: int) -> dict: ...


class StubWearableClient:
    """개발/테스트용 stub 구현입니다."""

    async def connect(self, user_id: int, device_token: str) -> None:
        raise NotImplementedError

    async def fetch_health_data(self, user_id: int) -> dict:
        raise NotImplementedError
