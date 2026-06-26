"""온보딩 단계 전이 정책.

온보딩 단계는 다음 순서로 진행된다.
CONSENT → WEARABLE → INITIAL_CHECKUP → CHECKUP_VERIFIED → COMPLETED

- CONSENT: 회원가입 직후. `POST /auth/policies/agree`로 약관 동의 시 WEARABLE로 전이.
- WEARABLE: `POST /onboarding/wearable`(CONNECT/SKIP)로 INITIAL_CHECKUP으로 전이.
- INITIAL_CHECKUP: 최초 검진 기록 업로드(Phase 3). 기록 생성 시 유지.
- CHECKUP_VERIFIED: 검진 결과 검증 완료(Phase 3). 검증 시 RecordService가 전이.
- COMPLETED: `POST /onboarding/complete`로 최종 완료.
"""

from app.domains.onboarding.exceptions import (
    InvalidOnboardingStepException,
    OnboardingAlreadyCompletedException,
)
from app.domains.user.models import OnboardingStep

# 현재 단계 → 다음 단계 매핑
NEXT_STEP: dict[OnboardingStep, OnboardingStep] = {
    OnboardingStep.CONSENT: OnboardingStep.WEARABLE,
    OnboardingStep.WEARABLE: OnboardingStep.INITIAL_CHECKUP,
    OnboardingStep.INITIAL_CHECKUP: OnboardingStep.CHECKUP_VERIFIED,
    OnboardingStep.CHECKUP_VERIFIED: OnboardingStep.COMPLETED,
}


def ensure_step(current_step: str, expected: OnboardingStep) -> None:
    """현재 단계가 기대 단계인지 검증한다.

    이미 완료된 경우 ONBOARDING_ALREADY_COMPLETED,
    그 외 불일치는 INVALID_ONBOARDING_STEP을 발생시킨다.
    """
    if current_step == OnboardingStep.COMPLETED.value:
        raise OnboardingAlreadyCompletedException()
    if current_step != expected.value:
        raise InvalidOnboardingStepException(
            message=f"이 작업은 {expected.value} 단계에서만 가능합니다. (현재: {current_step})"
        )
