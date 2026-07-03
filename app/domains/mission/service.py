import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.domains.mission.models import UserMission
from app.domains.mission.policy import local_date_for_timezone
from app.domains.mission.repository import MissionRepository
from app.domains.mission.schemas import Execution, MissionItem
from app.domains.user.repository import UserRepository

logger = logging.getLogger(__name__)


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
        return local_date_for_timezone(user.timezone if user is not None else None)

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
        """미션을 self-report로 완료 처리한다(멱등).

        본인 미션만 완료 가능하고, 이미 완료됐으면 no-op으로 XP 중복 지급을 막는다.
        완료 상태는 user_missions에 남아 build_pkg의 success_rate(14일창) 소스가 된다.
        캐릭터 경험치 지급/알림은 Phase 4에서 별도 연결한다.
        """
        mission = self._missions.get_for_user(mission_id, user_id)
        if mission is None:
            raise NotFoundException(message="미션을 찾을 수 없습니다.")
        if mission.status == "COMPLETED":
            return  # 멱등: 이미 완료 (재요청·더블탭 안전)
        mission.status = "COMPLETED"
        mission.completed_at = datetime.now(timezone.utc)
        self._db.commit()

    def verify_mission(self, user_id: int, mission_id: int) -> None:
        raise NotImplementedError

    def get_calendar(self, user_id: int):
        raise NotImplementedError

    def get_weekly_statistics(self, user_id: int):
        raise NotImplementedError

    def check_record_related_mission(self, user_id: int) -> None:
        """검진 등록 관련 미션을 확인하고 자동 완료합니다."""
        raise NotImplementedError
