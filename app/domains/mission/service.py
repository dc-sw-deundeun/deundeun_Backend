from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Literal, cast

from app.core.exceptions import NotFoundException
from app.domains.auth.exceptions import InvalidTokenException
from app.domains.mission.models import MissionTemplate, UserMission
from app.domains.mission.policy import local_date_for_timezone, week_range_for_date
from app.domains.mission.repository import MissionRepository
from app.domains.mission.schemas import (
    DayMissionStat,
    Execution,
    MissionNotificationResponse,
    MissionStatisticsSummary,
    MonthlyCalendarResponse,
    TodayMissionItem,
    TodayMissionsResponse,
    WeeklyStatisticsResponse,
)
from app.domains.user.models import User, UserStatus
from app.domains.user.repository import UserRepository


class MissionService:
    def __init__(self, repo: MissionRepository, user_repo: UserRepository) -> None:
        self.repo = repo
        self.user_repo = user_repo

    def _require_active_user(self, user_id: int) -> User:
        user = self.user_repo.find_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()
        return user

    def get_today_missions(self, user_id: int) -> TodayMissionsResponse:
        """유저 로컬 '오늘' 배정 미션(템플릿 기반 + 엔진 생성분)과 완료 집계."""
        user = self._require_active_user(user_id)
        return self._missions_for_date(user_id, local_date_for_timezone(user.timezone))

    def get_missions_for_date(self, user_id: int, target_date: date) -> TodayMissionsResponse:
        """특정 날짜의 배정 미션과 완료 집계(월간 캘린더에서 날짜 탭 → 상세)."""
        self._require_active_user(user_id)
        return self._missions_for_date(user_id, target_date)

    def _missions_for_date(self, user_id: int, target_date: date) -> TodayMissionsResponse:
        rows = self.repo.list_for_date_with_template(user_id, target_date)
        items = [self._to_item(mission, template) for mission, template in rows]
        return TodayMissionsResponse(
            date=target_date,
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
            # DB status는 str이지만 실제 값은 ASSIGNED|COMPLETED뿐(모델 코드 전체가 이 두 값만 씀).
            status=cast(Literal["ASSIGNED", "COMPLETED"], m.status),
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
        gain_exp()가 같은 세션을 commit하므로 미션 상태 + XP 지급이 원자적으로 저장된다.
        gain_exp() 실패 시 명시적 rollback으로 미션 상태 flush도 함께 버린다(재시도 안전).
        """
        mission = self.repo.get_for_user(mission_id, user_id)
        if mission is None:
            raise NotFoundException(message="미션을 찾을 수 없습니다.")
        if mission.status == "COMPLETED":
            return  # 멱등: 이미 완료 (재요청·더블탭 안전)
        mission.status = "COMPLETED"
        mission.completed_at = datetime.now(timezone.utc)
        if mission.xp_reward > 0:
            from app.domains.character.repository import CharacterRepository
            from app.domains.character.service import CharacterService

            try:
                CharacterService(CharacterRepository(self.repo._db)).gain_exp(
                    user_id=user_id,
                    amount=mission.xp_reward,
                    reason="mission_complete",
                    source="mission",
                    source_id=str(mission_id),
                )
            except Exception:
                self.repo._db.rollback()
                raise
        else:
            self.repo.commit()

    def verify_mission(self, user_id: int, mission_id: int) -> None:
        raise NotImplementedError

    def send_mission_notification(
        self, user_id: int, mission_id: int
    ) -> MissionNotificationResponse:
        """본인 미션의 리마인드 알림을 발송한다.

        mission_alarm_enabled=false면 스킵(에러 아님, sent=False). source_id=미션id인 유니크
        제약 덕에 같은 미션 재요청은 멱등 — 새 알림이 아니라 기존 알림의 id를 그대로 반환한다.
        """
        from app.domains.notification.repository import NotificationRepository
        from app.domains.notification.service import NotificationService

        found = self.repo.get_for_user_with_template(mission_id, user_id)
        if found is None:
            raise NotFoundException(message="미션을 찾을 수 없습니다.")
        mission, template = found
        item = self._to_item(mission, template)

        notif_repo = NotificationRepository(self.repo._db)
        pref = notif_repo.find_preference_by_user_id(user_id)
        if pref is not None and not pref.mission_alarm_enabled:
            return MissionNotificationResponse(
                sent=False, reason="미션 알림이 꺼져 있습니다(mission_alarm_enabled=false)."
            )

        body = (
            f"{item.execution.time} 예정 — 지금 확인해보세요."
            if item.execution.time
            else "지금 확인해보세요."
        )
        notification = NotificationService(notif_repo).notify_mission_reminder(
            user_id=user_id,
            mission_id=mission_id,
            title=item.title or "오늘의 미션",
            body=body,
        )
        return MissionNotificationResponse(sent=True, notification_id=notification.id)

    def get_weekly_statistics(
        self, user_id: int, ref_date: date | None = None
    ) -> WeeklyStatisticsResponse:
        """ref_date(없으면 유저 로컬 오늘)가 속한 주(월~일)의 일별·합계 집계."""
        user = self._require_active_user(user_id)
        ref = ref_date or local_date_for_timezone(user.timezone)
        start, end = week_range_for_date(ref)
        agg = self.repo.daily_counts_for_range(user_id, start, end)
        days = []
        d = start
        while d <= end:
            total, completed = agg.get(d, (0, 0))
            days.append(DayMissionStat(date=d, total=total, completed=completed))
            d += timedelta(days=1)
        return WeeklyStatisticsResponse(
            week_start=start,
            week_end=end,
            total=sum(day.total for day in days),
            completed=sum(day.completed for day in days),
            days=days,
        )

    def get_monthly_calendar(self, user_id: int, year: int, month: int) -> MonthlyCalendarResponse:
        """해당 월의 미션이 있는 날만 일별 집계(캘린더 점 표시용)."""
        self._require_active_user(user_id)
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        agg = self.repo.daily_counts_for_range(user_id, start, end)
        days = [
            DayMissionStat(date=d, total=total, completed=completed)
            for d, (total, completed) in sorted(agg.items())
        ]
        return MonthlyCalendarResponse(year=year, month=month, days=days)

    def get_statistics_summary(self, user_id: int) -> MissionStatisticsSummary:
        """전체 기간 총 배정·완료 수 + 완성도."""
        self._require_active_user(user_id)
        total, completed = self.repo.all_time_totals(user_id)
        rate = completed / total if total else 0.0
        return MissionStatisticsSummary(
            total_assigned=total, total_completed=completed, completion_rate=rate
        )

    def check_record_related_mission(self, user_id: int) -> None:
        """검진 등록 관련 미션을 확인하고 자동 완료합니다."""
        raise NotImplementedError
