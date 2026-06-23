class EmailDeliveryException(Exception):
    """SMTP 이메일 발송 실패."""

    def __init__(self, message: str = "이메일 발송에 실패했습니다.") -> None:
        super().__init__(message)
