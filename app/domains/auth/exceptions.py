from app.core.exceptions import AppException


class InvalidCredentialsException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="이메일 또는 비밀번호가 올바르지 않습니다.",
            error_code="INVALID_CREDENTIALS",
        )


class EmailAlreadyExistsException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            message="이미 사용 중인 이메일입니다.",
            error_code="EMAIL_ALREADY_EXISTS",
        )


class InvalidTokenException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="유효하지 않거나 만료된 토큰입니다.",
            error_code="INVALID_TOKEN",
        )


class NotVerifiedException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=403, message="이메일 인증이 필요합니다.", error_code="NOT_VERIFIED"
        )


class ConsentRequiredException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=403, message="필수 약관 동의가 필요합니다.", error_code="CONSENT_REQUIRED"
        )


class WeakPasswordException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            message="비밀번호는 8자 이상이며 영문·숫자·특수문자를 포함해야 합니다.",
            error_code="WEAK_PASSWORD",
        )


class InvalidVerificationCodeException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            message="인증 코드가 올바르지 않습니다.",
            error_code="INVALID_VERIFICATION_CODE",
        )


class VerificationCodeExpiredException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            message="인증 코드가 만료되었습니다. 다시 요청해 주세요.",
            error_code="VERIFICATION_CODE_EXPIRED",
        )


class VerificationAttemptsExceededException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            message="인증 시도 횟수를 초과했습니다. 코드를 다시 요청해 주세요.",
            error_code="VERIFICATION_ATTEMPTS_EXCEEDED",
        )


class ResendTooSoonException(AppException):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            status_code=429,
            message="인증 코드는 잠시 후 다시 요청할 수 있습니다.",
            error_code="RESEND_TOO_SOON",
        )
        self.retry_after_seconds = retry_after_seconds


class AccountLockedException(AppException):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            status_code=423,
            message="로그인 시도가 많아 계정이 일시 잠금되었습니다.",
            error_code="ACCOUNT_LOCKED",
        )
        self.retry_after_seconds = retry_after_seconds
