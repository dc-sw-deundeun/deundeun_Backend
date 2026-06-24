import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class EmailClient(Protocol):
    """이메일 발송 인터페이스 (SMTP / Stub 교체 가능)."""

    async def send_verification_email(self, to: str, code: str) -> None: ...

    async def send_password_reset_email(self, to: str, code: str) -> None: ...

    async def send_email(self, to: str, subject: str, body_html: str) -> None: ...


class StubEmailClient:
    """테스트·로컬 개발용 no-op 구현입니다."""

    async def send_verification_email(self, to: str, code: str) -> None:
        logger.info("[StubEmailClient] 인증 코드 (%s) → %s", code, to)

    async def send_password_reset_email(self, to: str, code: str) -> None:
        logger.info("[StubEmailClient] 비밀번호 재설정 코드 (%s) → %s", code, to)

    async def send_email(self, to: str, subject: str, body_html: str) -> None:
        logger.info("[StubEmailClient] 메일 발송 → %s | 제목: %s", to, subject)
