from datetime import date

from sqlalchemy.orm import Session

from app.domains.mission.models import UserMission
from app.domains.mission.repository import MissionRepository
from app.domains.mission.schemas import Execution, MissionItem
from app.domains.mission.timeutil import local_date
from app.domains.user.repository import UserRepository


class MissionService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._missions = MissionRepository(db)
        self._users = UserRepository(db)

    def get_today_missions(self, user_id: int) -> list[MissionItem]:
        """유저 로컬 '오늘'에 배정된 미션 목록. 아직 생성 전이면 빈 목록."""
        rows = self._missions.list_for_date(user_id, self._local_today(user_id))
        return [self._to_item(m) for m in rows]

    def _local_today(self, user_id: int) -> date:
        user = self._users.find_by_id(user_id)
        return local_date(user.timezone if user is not None else None)

    @staticmethod
    def _to_item(m: UserMission) -> MissionItem:
        payload = m.payload or {}
        return MissionItem(
            id=m.id,
            status=m.status,
            assigned_date=m.assigned_date,
            xp_reward=m.xp_reward,
            template_code=m.template_code,
            completed_at=m.completed_at,
            title=payload.get("title", ""),
            rationale=payload.get("rationale", ""),
            mission_type=payload.get("mission_type", ""),
            difficulty=payload.get("difficulty", 1),
            execution=Execution(**payload.get("execution", {})),
            grounded_on=payload.get("grounded_on", []),
            source=payload.get("source", "generated"),
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
