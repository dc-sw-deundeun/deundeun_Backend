from typing import Protocol


class EmailClient(Protocol):
    """이메일 발송 인터페이스입니다. SMTP/SendGrid 등으로 교체 가능합니다."""

    async def send_verification_email(self, to: str, token: str) -> None: ...

    async def send_password_reset_email(self, to: str, token: str) -> None: ...

    async def send_notification_email(self, to: str, subject: str, body: str) -> None: ...


class StubEmailClient:
    """개발/테스트용 stub 구현입니다."""

    async def send_verification_email(self, to: str, token: str) -> None:
        raise NotImplementedError

    async def send_password_reset_email(self, to: str, token: str) -> None:
        raise NotImplementedError

    async def send_notification_email(self, to: str, subject: str, body: str) -> None:
        raise NotImplementedError
