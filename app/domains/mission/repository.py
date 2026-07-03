from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.mission.constants import DEFAULT_MISSION_TEMPLATE_CODE
from app.domains.mission.models import MissionGenerationRun, MissionTemplate, UserMission
from app.domains.mission.schemas import GeneratedMission


class MissionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def find_template_by_code(self, code: str) -> MissionTemplate | None:
        return self._db.scalar(
            select(MissionTemplate).where(
                MissionTemplate.code == code,
                MissionTemplate.active.is_(True),
            )
        )

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
        try:
            with self._db.begin_nested():
                self._db.add(mission)
                self._db.flush()
            return mission
        except IntegrityError:
            existing = self.find_user_mission_for_date(user_id, template.id, assigned_date)
            if existing is not None:
                return existing
            raise

    def count_user_missions_for_date(self, user_id: int, assigned_date: date) -> int:
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

    # ----- 엔진 생성 미션 (인스턴스 저장) -----

    def list_for_date(self, user_id: int, assigned_date: date) -> list[UserMission]:
        return list(
            self._db.scalars(
                select(UserMission)
                .where(
                    UserMission.user_id == user_id,
                    UserMission.assigned_date == assigned_date,
                )
                .order_by(UserMission.id)
            )
        )

    def save_generated_mission(
        self, *, user_id: int, assigned_date: date, mission: GeneratedMission
    ) -> UserMission:
        """엔진 GeneratedMission을 user_missions 인스턴스로 저장(template_id=null, payload=전체)."""
        row = UserMission(
            user_id=user_id,
            template_id=None,
            assigned_date=assigned_date,
            status="ASSIGNED",
            xp_reward=0,
            template_code=mission.template_id,
            payload=mission.model_dump(mode="json"),
        )
        self._db.add(row)
        self._db.flush()
        return row

    def delete_incomplete_for_date(self, user_id: int, assigned_date: date) -> int:
        """그날 미완료(ASSIGNED) 미션 삭제 — 새 검진 재생성 시 완료분은 보존."""
        rows = list(
            self._db.scalars(
                select(UserMission).where(
                    UserMission.user_id == user_id,
                    UserMission.assigned_date == assigned_date,
                    UserMission.status == "ASSIGNED",
                )
            )
        )
        for row in rows:
            self._db.delete(row)
        self._db.flush()
        return len(rows)

    # ----- 완수 -----

    def get_for_user(self, mission_id: int, user_id: int) -> UserMission | None:
        return self._db.scalar(
            select(UserMission).where(
                UserMission.id == mission_id,
                UserMission.user_id == user_id,
            )
        )

    # ----- history (PKG success_rate / 변화) -----

    def success_rate(self, user_id: int, *, today: date, window_days: int = 14) -> float | None:
        """최근 window_days 중 '만료된(assigned_date < today)' 배정의 완료율. 만료분 없으면 None."""
        since = today - timedelta(days=window_days)
        base = (
            UserMission.user_id == user_id,
            UserMission.assigned_date >= since,
            UserMission.assigned_date < today,  # 오늘 배정분은 아직 만료 아님 → 제외
        )
        expired = self._db.scalar(select(func.count()).select_from(UserMission).where(*base)) or 0
        if expired == 0:
            return None
        completed = (
            self._db.scalar(
                select(func.count())
                .select_from(UserMission)
                .where(*base, UserMission.status == "COMPLETED")
            )
            or 0
        )
        return completed / expired

    def recent_template_codes(self, user_id: int, *, today: date, days: int = 3) -> list[str]:
        """최근 days간 배정된 template_code 목록(변화 유도용 exclude). None 제외."""
        since = today - timedelta(days=days)
        rows = self._db.scalars(
            select(UserMission.template_code)
            .where(
                UserMission.user_id == user_id,
                UserMission.assigned_date >= since,
                UserMission.template_code.is_not(None),
            )
            .distinct()
        )
        return [c for c in rows if c]


class MissionGenerationRunRepository:
    """미션 생성 멱등 로그 저장소 — 원자적 claim + 상태 기록."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def try_claim(self, user_id: int, generation_date: date, *, source: str = "scheduler") -> bool:
        """원자적 선점. 새로 꽂히면 True(생성 진행), 이미 있으면 False(스킵)."""
        stmt = (
            pg_insert(MissionGenerationRun)
            .values(
                user_id=user_id,
                generation_date=generation_date,
                status="pending",
                source=source,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "generation_date"])
            .returning(MissionGenerationRun.id)
        )
        claimed = self._db.execute(stmt).first() is not None
        self._db.flush()
        return claimed

    def mark(
        self,
        user_id: int,
        generation_date: date,
        status: str,
        *,
        mission_count: int | None = None,
        error_code: str | None = None,
    ) -> None:
        run = self._db.scalar(
            select(MissionGenerationRun).where(
                MissionGenerationRun.user_id == user_id,
                MissionGenerationRun.generation_date == generation_date,
            )
        )
        if run is None:
            return
        run.status = status
        run.attempts = (run.attempts or 0) + 1
        if mission_count is not None:
            run.mission_count = mission_count
        if error_code is not None:
            run.error_code = error_code
        self._db.flush()
