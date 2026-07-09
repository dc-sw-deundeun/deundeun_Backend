"""미션 조회 API — 주간/월간/날짜별/총계 (프론트 조회).

- policy.week_range_for_date: 월~일 주 범위(순수).
- repository.list_for_range / all_time_totals (DB).
- service: 주간 통계·월간 캘린더·날짜별 상세·총계 요약 (DB).
"""

from datetime import date

from app.domains.mission import policy
from app.domains.mission.models import UserMission
from app.domains.mission.repository import MissionRepository
from app.domains.mission.service import MissionService
from app.domains.user.repository import UserRepository
from tests.domains.pkg.test_service import _create_user


def _seed_mission(db, user_id: int, d: date, status: str = "ASSIGNED") -> None:
    db.add(
        UserMission(
            user_id=user_id,
            template_id=None,
            assigned_date=d,
            status=status,
            xp_reward=10,
            template_code=None,
            payload={"title": f"m-{d.isoformat()}", "mission_type": "exercise", "difficulty": 1},
        )
    )


def _svc(db) -> MissionService:
    return MissionService(MissionRepository(db), UserRepository(db))


# --- policy.week_range_for_date (순수) ---


def test_week_range_for_date_monday_to_sunday() -> None:
    # 2026-07-08은 수요일 → 주는 월(07-06)~일(07-12)
    start, end = policy.week_range_for_date(date(2026, 7, 8))
    assert start == date(2026, 7, 6)
    assert end == date(2026, 7, 12)


def test_week_range_for_date_on_monday() -> None:
    start, end = policy.week_range_for_date(date(2026, 7, 6))
    assert start == date(2026, 7, 6) and end == date(2026, 7, 12)


# --- repository ---


def test_list_for_range_inclusive_and_excludes_outside(db_session) -> None:
    _create_user(db_session, 31)
    _seed_mission(db_session, 31, date(2026, 7, 6))
    _seed_mission(db_session, 31, date(2026, 7, 12))
    _seed_mission(db_session, 31, date(2026, 7, 13))  # 범위 밖
    db_session.commit()
    rows = MissionRepository(db_session).list_for_range(31, date(2026, 7, 6), date(2026, 7, 12))
    dates = sorted(r.assigned_date for r in rows)
    assert dates == [date(2026, 7, 6), date(2026, 7, 12)]


def test_all_time_totals(db_session) -> None:
    _create_user(db_session, 32)
    for _ in range(3):
        _seed_mission(db_session, 32, date(2026, 7, 6), "ASSIGNED")
    for _ in range(2):
        _seed_mission(db_session, 32, date(2026, 7, 7), "COMPLETED")
    db_session.commit()
    total, completed = MissionRepository(db_session).all_time_totals(32)
    assert total == 5 and completed == 2


# --- service ---


def test_weekly_statistics(db_session) -> None:
    _create_user(db_session, 33)
    _seed_mission(db_session, 33, date(2026, 7, 6), "COMPLETED")
    _seed_mission(db_session, 33, date(2026, 7, 6), "ASSIGNED")
    _seed_mission(db_session, 33, date(2026, 7, 8), "ASSIGNED")
    _seed_mission(db_session, 33, date(2026, 7, 13), "COMPLETED")  # 다음 주 → 제외
    db_session.commit()
    res = _svc(db_session).get_weekly_statistics(33, ref_date=date(2026, 7, 8))
    assert res.week_start == date(2026, 7, 6) and res.week_end == date(2026, 7, 12)
    assert res.total == 3 and res.completed == 1
    assert len(res.days) == 7  # 월~일 전부
    by_date = {d.date: d for d in res.days}
    assert by_date[date(2026, 7, 6)].total == 2 and by_date[date(2026, 7, 6)].completed == 1
    assert by_date[date(2026, 7, 8)].total == 1
    assert by_date[date(2026, 7, 7)].total == 0  # 미션 없는 날은 0


def test_monthly_calendar(db_session) -> None:
    _create_user(db_session, 34)
    _seed_mission(db_session, 34, date(2026, 7, 6), "COMPLETED")
    _seed_mission(db_session, 34, date(2026, 7, 15), "ASSIGNED")
    _seed_mission(db_session, 34, date(2026, 8, 1), "ASSIGNED")  # 다음 달 → 제외
    db_session.commit()
    res = _svc(db_session).get_monthly_calendar(34, 2026, 7)
    assert res.year == 2026 and res.month == 7
    seen = {d.date: d for d in res.days}
    assert set(seen) == {date(2026, 7, 6), date(2026, 7, 15)}  # 미션 있는 날만
    assert seen[date(2026, 7, 6)].completed == 1


def test_missions_for_date(db_session) -> None:
    _create_user(db_session, 35)
    _seed_mission(db_session, 35, date(2026, 7, 6), "COMPLETED")
    _seed_mission(db_session, 35, date(2026, 7, 6), "ASSIGNED")
    db_session.commit()
    res = _svc(db_session).get_missions_for_date(35, date(2026, 7, 6))
    assert res.date == date(2026, 7, 6)
    assert res.total == 2 and res.completed == 1
    assert len(res.items) == 2


def test_statistics_summary(db_session) -> None:
    _create_user(db_session, 36)
    for _ in range(3):
        _seed_mission(db_session, 36, date(2026, 7, 6), "COMPLETED")
    for _ in range(2):
        _seed_mission(db_session, 36, date(2026, 7, 7), "ASSIGNED")
    db_session.commit()
    res = _svc(db_session).get_statistics_summary(36)
    assert res.total_assigned == 5 and res.total_completed == 3
    assert abs(res.completion_rate - 0.6) < 1e-9


def test_statistics_summary_no_missions(db_session) -> None:
    _create_user(db_session, 37)
    db_session.commit()
    res = _svc(db_session).get_statistics_summary(37)
    assert res.total_assigned == 0 and res.completion_rate == 0.0


# --- 라우터 통합(엔드포인트 연결·직렬화) ---


def _as_user(user_id: int):
    from app.core.dependencies import get_current_user
    from app.domains.user.schemas import CurrentUser
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)


def _clear_override():
    from app.core.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)


def test_weekly_endpoint(client, db_session) -> None:
    _create_user(db_session, 40)
    _seed_mission(db_session, 40, date(2026, 7, 6), "COMPLETED")
    db_session.commit()
    _as_user(40)
    try:
        res = client.get("/api/v1/missions/statistics/weekly?date=2026-07-08")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["week_start"] == "2026-07-06" and data["week_end"] == "2026-07-12"
        assert len(data["days"]) == 7
    finally:
        _clear_override()


def test_calendar_endpoint(client, db_session) -> None:
    _create_user(db_session, 41)
    _seed_mission(db_session, 41, date(2026, 7, 6), "COMPLETED")
    db_session.commit()
    _as_user(41)
    try:
        res = client.get("/api/v1/missions/calendar?year=2026&month=7")
        assert res.status_code == 200
        days = res.json()["data"]["days"]
        assert days == [{"date": "2026-07-06", "total": 1, "completed": 1}]
    finally:
        _clear_override()


def test_date_and_summary_endpoints(client, db_session) -> None:
    _create_user(db_session, 42)
    _seed_mission(db_session, 42, date(2026, 7, 6), "COMPLETED")
    _seed_mission(db_session, 42, date(2026, 7, 6), "ASSIGNED")
    db_session.commit()
    _as_user(42)
    try:
        res = client.get("/api/v1/missions/date/2026-07-06")
        assert res.status_code == 200
        assert res.json()["data"]["total"] == 2

        res = client.get("/api/v1/missions/statistics/summary")
        assert res.status_code == 200
        summary = res.json()["data"]
        assert summary["total_assigned"] == 2 and summary["total_completed"] == 1
    finally:
        _clear_override()
