from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domains.mission import policy
from app.domains.mission.models import MissionGenerationRun, MissionTemplate, UserMission
from app.domains.mission.schemas import GeneratedMission, History


class MissionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def commit(self) -> None:
        self._db.commit()

    def find_template_by_code(self, code: str) -> MissionTemplate | None:
        return self._db.scalar(
            select(MissionTemplate).where(
                MissionTemplate.code == code,
                MissionTemplate.active.is_(True),
            )
        )

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

    def list_for_date_with_template(
        self, user_id: int, assigned_date: date
    ) -> list[tuple[UserMission, MissionTemplate | None]]:
        """조회용(GET /today): 템플릿 기반(#24 기본미션)·엔진 생성 미션을 함께 반환.

        엔진 생성 미션은 template_id가 NULL이라 INNER JOIN이면 통째로 빠진다 — LEFT JOIN으로
        두 출처를 공존시킨다(템플릿 없으면 template=None, 서비스가 payload로 필드를 채운다).
        """
        rows = self._db.execute(
            select(UserMission, MissionTemplate)
            .outerjoin(MissionTemplate, UserMission.template_id == MissionTemplate.id)
            .where(
                UserMission.user_id == user_id,
                UserMission.assigned_date == assigned_date,
            )
            .order_by(UserMission.id)
        ).all()
        return [(mission, template) for mission, template in rows]

    def list_for_range(self, user_id: int, start: date, end: date) -> list[UserMission]:
        """[start, end] 구간(양끝 포함) 배정 미션 — 주간/월간 집계용."""
        return list(
            self._db.scalars(
                select(UserMission)
                .where(
                    UserMission.user_id == user_id,
                    UserMission.assigned_date >= start,
                    UserMission.assigned_date <= end,
                )
                .order_by(UserMission.assigned_date, UserMission.id)
            )
        )

    def all_time_totals(self, user_id: int) -> tuple[int, int]:
        """(전체 배정 수, 완료 수) — 총 완료 통계/완성도용."""
        total = (
            self._db.scalar(
                select(func.count()).select_from(UserMission).where(UserMission.user_id == user_id)
            )
            or 0
        )
        completed = (
            self._db.scalar(
                select(func.count())
                .select_from(UserMission)
                .where(UserMission.user_id == user_id, UserMission.status == "COMPLETED")
            )
            or 0
        )
        return total, completed

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
            xp_reward=policy.xp_for_difficulty(mission.difficulty),
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

    def recent_mission_titles(
        self, user_id: int, *, today: date, days: int = 14, limit: int = 10
    ) -> list[str]:
        """최근 days간 배정 미션의 title 목록(최신순·중복 제거). payload 없는 행은 제외."""
        since = today - timedelta(days=days)
        rows = self._db.scalars(
            select(UserMission.payload)
            .where(
                UserMission.user_id == user_id,
                UserMission.assigned_date >= since,
                UserMission.payload.is_not(None),
            )
            .order_by(UserMission.assigned_date.desc(), UserMission.id.desc())
        )
        titles: list[str] = []
        seen: set[str] = set()
        for payload in rows:
            title = (payload or {}).get("title")
            if title and title not in seen:
                seen.add(title)
                titles.append(title)
            if len(titles) >= limit:
                break
        return titles

    def build_history(self, user_id: int, *, today: date) -> History:
        """미션 완료 이력 → PKG.history(동적). 생성 시점에 계산해 PKG에 overlay한다."""
        return History(
            success_rate=self.success_rate(user_id, today=today),
            recent_mission_titles=self.recent_mission_titles(user_id, today=today),
        )


class MissionGenerationRunRepository:
    """미션 생성 멱등 로그 저장소 — 원자적 claim + 상태 기록."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def try_claim(self, user_id: int, generation_date: date, *, source: str = "scheduler") -> bool:
        """원자적 선점. 새로 꽂히면 True(생성 진행), 이미 있으면 False(스킵).

        claim row는 **즉시 커밋**한다 — 생성 실패 시 서비스가 rollback해도 pending row가
        살아남아 mark("failed")로 상태·attempts를 남길 수 있다(관측·재시도 계약 유지).
        """
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
        self._db.commit()
        return claimed

    def delete_for_date(self, user_id: int, generation_date: date) -> int:
        """유저·날짜 생성 로그 삭제 — 새 검진 재생성 시 claim을 다시 열어준다."""
        rows = list(
            self._db.scalars(
                select(MissionGenerationRun).where(
                    MissionGenerationRun.user_id == user_id,
                    MissionGenerationRun.generation_date == generation_date,
                )
            )
        )
        for row in rows:
            self._db.delete(row)
        self._db.flush()
        return len(rows)

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
