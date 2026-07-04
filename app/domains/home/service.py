from app.domains.auth.exceptions import InvalidTokenException
from app.domains.character.service import CharacterService
from app.domains.home.schemas import HomeResponse, HomeSummaryResponse, HomeUserBlock
from app.domains.mission.service import MissionService
from app.domains.user.models import OnboardingStep, UserStatus
from app.domains.user.repository import UserRepository


class HomeService:
    """홈 화면용 Aggregation Service입니다. DB 모델 없이 각 도메인 서비스를 조합합니다."""

    def __init__(
        self,
        user_repo: UserRepository,
        character_service: CharacterService,
        mission_service: MissionService,
    ) -> None:
        self.user_repo = user_repo
        self.character_service = character_service
        self.mission_service = mission_service

    def get_home(self, user_id: int) -> HomeResponse:
        """홈 메인 데이터를 반환합니다.

        조합 대상:
        - UserService: 사용자 정보
        - CharacterService: 캐릭터 상태
        - MissionService: 오늘의 미션 요약
        - RecordService: 최근 검진 기록 요약
        - NotificationService: 알림 요약
        """
        user = self.user_repo.find_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()

        character = self.character_service.get_my_character(user_id)
        today_missions = self.mission_service.get_today_missions(user_id)
        onboarding_step = getattr(user.onboarding_step, "value", user.onboarding_step)

        return HomeResponse(
            user=HomeUserBlock(
                id=user.id,
                nickname=user.nickname,
                onboarding_step=onboarding_step,
                onboarding_completed=onboarding_step == OnboardingStep.COMPLETED.value,
            ),
            character=character,
            today_missions=today_missions,
            unread_notification_count=0,
        )

    def get_summary(self, user_id: int) -> HomeSummaryResponse:
        """홈 요약 데이터를 반환합니다."""
        home = self.get_home(user_id)
        return HomeSummaryResponse(
            nickname=home.user.nickname,
            level=home.character.level,
            total_exp=home.character.total_exp,
            progress_ratio=home.character.progress_ratio,
            owned_animal_count=len(home.character.owned_animals),
            today_mission_total=home.today_missions.total,
            today_mission_completed=home.today_missions.completed,
            unread_notification_count=home.unread_notification_count,
        )
