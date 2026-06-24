import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTPException

from app.core.config import settings
from app.infrastructure.email.exceptions import EmailDeliveryException

_SMTP_TIMEOUT_SECONDS = 10

_VERIFICATION_TEMPLATE = """\
<html>
<body>
  <p>안녕하세요, 든든 앱입니다.</p>
  <p>이메일 인증 코드: <strong>{code}</strong></p>
  <p>이 코드는 10분 후 만료됩니다.</p>
</body>
</html>
"""

_PASSWORD_RESET_TEMPLATE = """\
<html>
<body>
  <p>안녕하세요, 든든 앱입니다.</p>
  <p>비밀번호 재설정 코드: <strong>{code}</strong></p>
  <p>이 코드는 10분 후 만료됩니다.</p>
  <p>본인이 요청하지 않은 경우 이 메일을 무시하세요.</p>
</body>
</html>
"""


class SmtpEmailClient:
    """Gmail SMTP TLS를 이용한 실제 이메일 발송 클라이언트입니다."""

    def __init__(self) -> None:
        if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
            raise RuntimeError(
                "SMTP 설정이 완료되지 않았습니다. "
                "SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD 환경변수를 확인하세요."
            )
        if not settings.smtp_from:
            raise RuntimeError(
                "SMTP_FROM 환경변수가 설정되지 않았습니다. 발신자 이메일 주소를 확인하세요."
            )
        smtp_from = settings.smtp_from
        self.smtp_host = settings.smtp_host
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_from = smtp_from

    def _connect_smtp(self):
        if settings.smtp_port == 465:
            return smtplib.SMTP_SSL(
                self.smtp_host, settings.smtp_port, timeout=_SMTP_TIMEOUT_SECONDS
            )
        return smtplib.SMTP(self.smtp_host, settings.smtp_port, timeout=_SMTP_TIMEOUT_SECONDS)

    def _send_sync(self, to: str, subject: str, body_html: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_from
        msg["To"] = to
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            with self._connect_smtp() as smtp:
                if settings.smtp_port != 465 and settings.smtp_use_tls:
                    smtp.starttls()
                smtp.login(self.smtp_username, self.smtp_password)
                smtp.sendmail(self.smtp_from, to, msg.as_string())
        except (SMTPException, OSError) as e:
            raise EmailDeliveryException(f"이메일 발송 실패: {e}") from e

    async def send_email(self, to: str, subject: str, body_html: str) -> None:
        await asyncio.to_thread(self._send_sync, to, subject, body_html)

    async def send_verification_email(self, to: str, code: str) -> None:
        await self.send_email(
            to=to,
            subject="[든든] 이메일 인증 코드",
            body_html=_VERIFICATION_TEMPLATE.format(code=code),
        )

    async def send_password_reset_email(self, to: str, code: str) -> None:
        await self.send_email(
            to=to,
            subject="[든든] 비밀번호 재설정 코드",
            body_html=_PASSWORD_RESET_TEMPLATE.format(code=code),
        )
