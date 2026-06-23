from typing import Optional, Protocol


class PushClient(Protocol):
    """푸시 알림 발송 인터페이스입니다. FCM 등으로 교체 가능합니다."""

    async def send(
        self, token: str, title: str, body: str, data: Optional[dict] = None
    ) -> None: ...


class StubPushClient:
    """개발/테스트용 stub 구현입니다."""

    async def send(self, token: str, title: str, body: str, data: Optional[dict] = None) -> None:
        raise NotImplementedError
