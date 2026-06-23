"""SmtpEmailClient 단위 테스트 — smtplib.SMTP를 mock으로 패치합니다."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.email.smtp_email_client import SmtpEmailClient


@pytest.fixture
def smtp_settings(monkeypatch):
    """SMTP 설정을 임시로 주입합니다."""
    monkeypatch.setattr("app.core.config.settings.smtp_host", "smtp.gmail.com")
    monkeypatch.setattr("app.core.config.settings.smtp_port", 587)
    monkeypatch.setattr("app.core.config.settings.smtp_username", "test@gmail.com")
    monkeypatch.setattr("app.core.config.settings.smtp_password", "test-password")
    monkeypatch.setattr("app.core.config.settings.smtp_from", "test@gmail.com")
    monkeypatch.setattr("app.core.config.settings.smtp_use_tls", True)


def test_smtp_send_verification_email(smtp_settings) -> None:
    mock_smtp_instance = MagicMock()

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        client = SmtpEmailClient()
        asyncio.run(client.send_verification_email(to="user@example.com", code="654321"))

    mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587)
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with("test@gmail.com", "test-password")
    mock_smtp_instance.sendmail.assert_called_once()


def test_smtp_missing_settings_raises(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.smtp_host", None)
    monkeypatch.setattr("app.core.config.settings.smtp_username", None)
    monkeypatch.setattr("app.core.config.settings.smtp_password", None)

    with pytest.raises(RuntimeError, match="SMTP 설정"):
        SmtpEmailClient()
