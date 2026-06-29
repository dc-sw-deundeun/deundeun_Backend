from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.mission.constants import DEFAULT_MISSION_TEMPLATE_CODE
from app.domains.mission.models import MissionTemplate, UserMission


def local_date_for_timezone(timezone_name: str, *, now: datetime | None = None) -> date:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(ZoneInfo(timezone_name)).date()


class MissionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def find_template_by_code(self, code: str) -> MissionTemplate | None:
        return self._db.scalar(select(MissionTemplate).where(MissionTemplate.code == code))

    def find_default_template(self) -> MissionTemplate | None:
        return self.find_template_by_code(DEFAULT_MISSION_TEMPLATE_CODE)

    def find_user_mission_for_date(
        self, user_id: int, template_id: int, assigned_date: date
    ) -> UserMission | None:
        return self._db.scalar(
            select(UserMission).where(
                UserMission.user_id == user_id,
                UserMission.template_id == template_id,
                UserMission.assigned_date == assigned_date,
            )
        )

    def create_user_mission(
        self,
        *,
        user_id: int,
        template: MissionTemplate,
        source_record_id: int | None,
        assigned_date: date,
    ) -> UserMission:
        mission = UserMission(
            user_id=user_id,
            template_id=template.id,
            source_record_id=source_record_id,
            assigned_date=assigned_date,
            status="ASSIGNED",
            xp_reward=template.default_xp,
        )
        self._db.add(mission)
        self._db.flush()
        return mission

    def count_user_missions_for_date(self, user_id: int, assigned_date: date) -> int:
        from sqlalchemy import func

        return (
            self._db.scalar(
                select(func.count())
                .select_from(UserMission)
                .where(
                    UserMission.user_id == user_id,
                    UserMission.assigned_date == assigned_date,
                )
            )
            or 0
        )
