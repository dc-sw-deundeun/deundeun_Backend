class NotificationSender:
    """알림 발송을 담당합니다. infrastructure/email, infrastructure/push로 위임합니다."""

    async def send_push(self, user_id: int, title: str, body: str) -> None:
        raise NotImplementedError

    async def send_email(self, to: str, subject: str, body: str) -> None:
        raise NotImplementedError
