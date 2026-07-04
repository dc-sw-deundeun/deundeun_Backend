from app.domains.auth.exceptions import InvalidTokenException
from app.domains.mission.policy import local_date_for_timezone
from app.domains.mission.repository import MissionRepository
from app.domains.mission.schemas import TodayMissionItem, TodayMissionsResponse
from app.domains.user.models import UserStatus
from app.domains.user.repository import UserRepository


class MissionService:
    def __init__(self, repo: MissionRepository, user_repo: UserRepository) -> None:
        self.repo = repo
        self.user_repo = user_repo

    def get_today_missions(self, user_id: int) -> TodayMissionsResponse:
        user = self.user_repo.find_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()

        today = local_date_for_timezone(user.timezone)
        rows = self.repo.list_user_missions_for_date(user_id, today)
        items = [
            TodayMissionItem(
                mission_id=mission.id,
                template_code=template.code,
                title=template.title,
                description=template.description,
                category=template.category,
                verification_mode=template.verification_mode,
                xp_reward=mission.xp_reward,
                status=mission.status,
                assigned_date=mission.assigned_date,
                source_record_id=mission.source_record_id,
            )
            for mission, template in rows
        ]
        return TodayMissionsResponse(
            date=today,
            total=len(items),
            completed=sum(1 for item in items if item.status == "COMPLETED"),
            items=items,
        )

    def complete_mission(self, user_id: int, mission_id: int) -> None:
        """미션을 완료합니다.

        흐름:
        1. 미션 존재 여부 확인
        2. 해당 사용자의 미션인지 확인
        3. 이미 완료된 미션인지 확인
        4. 완료 상태로 변경
        5. CharacterService.gain_exp() 호출 (Phase 4에서 연결)
        6. NotificationService 로그 저장
        """
        raise NotImplementedError

    def verify_mission(self, user_id: int, mission_id: int) -> None:
        raise NotImplementedError

    def get_calendar(self, user_id: int):
        raise NotImplementedError

    def get_weekly_statistics(self, user_id: int):
        raise NotImplementedError

    def check_record_related_mission(self, user_id: int) -> None:
        """검진 등록 관련 미션을 확인하고 자동 완료합니다."""
        raise NotImplementedError
