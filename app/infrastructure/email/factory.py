from app.core.config import settings
from app.infrastructure.email.email_client import EmailClient, StubEmailClient
from app.infrastructure.email.smtp_email_client import SmtpEmailClient


def get_email_client() -> EmailClient:
    """SMTP 설정이 모두 있으면 SmtpEmailClient, 없으면 StubEmailClient를 반환합니다."""
    if (
        settings.smtp_host
        and settings.smtp_username
        and settings.smtp_password
        and settings.smtp_from
    ):
        return SmtpEmailClient()
    return StubEmailClient()
