from app.core.exceptions import AppException


class InvalidOnboardingStepException(AppException):
    def __init__(self, message: str = "현재 온보딩 단계에서 수행할 수 없는 요청입니다.") -> None:
        super().__init__(
            status_code=409,
            message=message,
            error_code="INVALID_ONBOARDING_STEP",
        )


class OnboardingAlreadyCompletedException(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            message="이미 온보딩을 완료했습니다.",
            error_code="ONBOARDING_ALREADY_COMPLETED",
        )


class OnboardingIncompleteException(AppException):
    """완료 요청 시 선행 단계(검진 인증 등)가 끝나지 않은 경우."""

    def __init__(self, message: str = "온보딩을 완료하기 위한 선행 단계가 남아 있습니다.") -> None:
        super().__init__(
            status_code=409,
            message=message,
            error_code="ONBOARDING_INCOMPLETE",
        )
