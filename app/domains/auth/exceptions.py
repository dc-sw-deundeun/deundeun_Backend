from app.core.exceptions import AppException


class InvalidCredentialsException(AppException):
    def __init__(self) -> None:
        super().__init__(status_code=401, message="이메일 또는 비밀번호가 올바르지 않습니다.", error_code="INVALID_CREDENTIALS")


class EmailAlreadyExistsException(AppException):
    def __init__(self) -> None:
        super().__init__(status_code=409, message="이미 사용 중인 이메일입니다.", error_code="EMAIL_ALREADY_EXISTS")


class InvalidTokenException(AppException):
    def __init__(self) -> None:
        super().__init__(status_code=400, message="유효하지 않거나 만료된 토큰입니다.", error_code="INVALID_TOKEN")
