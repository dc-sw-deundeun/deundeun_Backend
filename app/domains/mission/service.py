from datetime import datetime, timezone

from app.core.exceptions import NotFoundException
from app.domains.auth.exceptions import InvalidTokenException
from app.domains.mission.models import MissionTemplate, UserMission
from app.domains.mission.policy import local_date_for_timezone
from app.domains.mission.repository import MissionRepository
from app.domains.mission.schemas import Execution, TodayMissionItem, TodayMissionsResponse
from app.domains.user.models import UserStatus
from app.domains.user.repository import UserRepository


class MissionService:
    def __init__(self, repo: MissionRepository, user_repo: UserRepository) -> None:
        self.repo = repo
        self.user_repo = user_repo

    def get_today_missions(self, user_id: int) -> TodayMissionsResponse:
        """유저 로컬 '오늘' 배정 미션(템플릿 기반 + 엔진 생성분)과 완료 집계."""
        user = self.user_repo.find_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()

        today = local_date_for_timezone(user.timezone)
        rows = self.repo.list_for_date_with_template(user_id, today)
        items = [self._to_item(mission, template) for mission, template in rows]
        return TodayMissionsResponse(
            date=today,
            total=len(items),
            completed=sum(1 for item in items if item.status == "COMPLETED"),
            items=items,
        )

    @staticmethod
    def _to_item(m: UserMission, template: MissionTemplate | None) -> TodayMissionItem:
        payload = m.payload or {}
        return TodayMissionItem(
            mission_id=m.id,
            template_code=m.template_code or (template.code if template else None),
            title=template.title if template else payload.get("title", ""),
            status=m.status,
            assigned_date=m.assigned_date,
            xp_reward=m.xp_reward,
            completed_at=m.completed_at,
            source_record_id=m.source_record_id,
            rationale=payload.get("rationale", ""),
            mission_type=payload.get("mission_type", ""),
            difficulty=payload.get("difficulty", 1),
            execution=Execution(**payload.get("execution", {})),
            grounded_on=payload.get("grounded_on", []),
            source=payload.get("source", "generated"),
            description=template.description if template else None,
            category=template.category if template else None,
            verification_mode=template.verification_mode if template else None,
        )

    def complete_mission(self, user_id: int, mission_id: int) -> None:
        """미션을 self-report로 완료 처리한다(멱등).

        본인 미션만 완료 가능하고, 이미 완료됐으면 no-op으로 XP 중복 지급을 막는다.
        완료 상태는 user_missions에 남아 build_pkg의 success_rate(14일창) 소스가 된다.
        캐릭터 경험치 지급/알림은 Phase 4에서 별도 연결한다.
        """
        mission = self.repo.get_for_user(mission_id, user_id)
        if mission is None:
            raise NotFoundException(message="미션을 찾을 수 없습니다.")
        if mission.status == "COMPLETED":
            return  # 멱등: 이미 완료 (재요청·더블탭 안전)
        mission.status = "COMPLETED"
        mission.completed_at = datetime.now(timezone.utc)
        self.repo.commit()

    def verify_mission(self, user_id: int, mission_id: int) -> None:
        raise NotImplementedError

    def get_calendar(self, user_id: int):
        raise NotImplementedError

    def get_weekly_statistics(self, user_id: int):
        raise NotImplementedError

    def check_record_related_mission(self, user_id: int) -> None:
        """검진 등록 관련 미션을 확인하고 자동 완료합니다."""
        raise NotImplementedError
