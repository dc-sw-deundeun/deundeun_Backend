"""온보딩 완료 후처리 훅."""

import logging

logger = logging.getLogger(__name__)


def on_onboarding_complete(user_id: int) -> None:
    """온보딩 완료 직후 캐릭터 기본 프로필을 준비합니다."""
    try:
        from app.database.session import session_scope
        from app.domains.character.repository import CharacterRepository
        from app.domains.character.service import CharacterService

        with session_scope() as db:
            CharacterService(CharacterRepository(db)).get_my_character(user_id)
    except Exception:
        logger.exception("failed to prepare character profile for user_id=%s", user_id)
        return

    logger.info("onboarding completed and character profile prepared for user_id=%s", user_id)


def advance_to_checkup_verified(user) -> bool:
    """검진 검수 완료 시 INITIAL_CHECKUP → CHECKUP_VERIFIED 전이. 전이 시 True."""
    from app.domains.user.models import OnboardingStep

    if user.onboarding_step != OnboardingStep.INITIAL_CHECKUP.value:
        return False
    user.onboarding_step = OnboardingStep.CHECKUP_VERIFIED
    logger.info("onboarding step advanced to CHECKUP_VERIFIED for user_id=%s", user.id)
    return True
