"""온보딩 완료 후처리 훅.

온보딩이 완료(COMPLETED)될 때 실행할 후속 작업의 확장 지점이다.
예: 초기 미션 생성(Phase 5), 환영 알림 발송(Phase 7) 등.
현재는 no-op이며 후속 Phase에서 실제 구현을 연결한다.
"""

import logging

logger = logging.getLogger(__name__)


def on_onboarding_complete(user_id: int) -> None:
    """온보딩 완료 직후 호출되는 훅 (현재는 로깅만)."""
    logger.info("onboarding completed for user_id=%s (post-complete hooks pending)", user_id)


def advance_to_checkup_verified(user) -> bool:
    """검진 검수 완료 시 INITIAL_CHECKUP → CHECKUP_VERIFIED 전이. 전이 시 True."""
    from app.domains.user.models import OnboardingStep

    if user.onboarding_step != OnboardingStep.INITIAL_CHECKUP.value:
        return False
    user.onboarding_step = OnboardingStep.CHECKUP_VERIFIED
    logger.info("onboarding step advanced to CHECKUP_VERIFIED for user_id=%s", user.id)
    return True
