"""미션 생성 서비스 — 멱등 생성, PKG 소비, user_missions 인스턴스 저장.

LLM 키를 제거해 결정적 fallback(mission_pool 템플릿)으로 돌린다 — 실 CLOVA 호출 방지.
DB 픽스처(db_session, Postgres testcontainers) 사용.
"""

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.domains.mission.generation_service import MissionGenerationService
from app.domains.mission.models import MissionGenerationRun
from app.domains.mission.policy import local_date_for_timezone
from app.domains.mission.repository import MissionRepository
from app.domains.mission.scheduler import run_daily_generation_tick
from app.domains.mission.schemas import GeneratedMission
from app.domains.mission.service import MissionService
from app.domains.pkg.dependencies import build_pkg_service
from tests.domains.pkg.test_service import _create_user, _seed_record

_TODAY = date(2026, 7, 3)


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "clova_studio_api_key", None)


def _gen(db, user_id: int) -> bool:
    return asyncio.run(
        MissionGenerationService(db).generate_for_user(user_id, _TODAY, source="scheduler")
    )


def _gen_run(db, user_id: int) -> MissionGenerationRun | None:
    return db.scalar(select(MissionGenerationRun).where(MissionGenerationRun.user_id == user_id))


def test_generate_creates_missions_and_logs(db_session) -> None:
    _create_user(db_session, 101)
    _seed_record(db_session, 101, [("systolic_bp", "150"), ("fasting_glucose", "130")])

    created = _gen(db_session, 101)

    assert created is True
    missions = MissionRepository(db_session).list_for_date(101, _TODAY)
    assert len(missions) >= 1
    first = missions[0]
    assert first.status == "ASSIGNED"
    assert first.template_id is None  # 엔진 생성분은 DB 템플릿 없음
    assert first.payload and first.payload["title"]  # 인스턴스 payload 저장
    assert first.template_code  # 변화/provenance용 문자열 id
    run = _gen_run(db_session, 101)
    assert run is not None and run.status == "generated"
    assert run.mission_count == len(missions)


def test_generate_is_idempotent(db_session) -> None:
    _create_user(db_session, 102)
    _seed_record(db_session, 102, [("systolic_bp", "150")])

    assert _gen(db_session, 102) is True
    n1 = len(MissionRepository(db_session).list_for_date(102, _TODAY))
    assert _gen(db_session, 102) is False  # 두 번째는 claim 실패 → 스킵
    n2 = len(MissionRepository(db_session).list_for_date(102, _TODAY))
    assert n1 == n2 and n1 >= 1  # 중복 생성 없음


def test_generate_skips_without_verified_checkup(db_session) -> None:
    _create_user(db_session, 103)  # 검진 없음

    assert _gen(db_session, 103) is False
    assert MissionRepository(db_session).list_for_date(103, _TODAY) == []
    run = _gen_run(db_session, 103)
    assert run is not None and run.status == "skipped"


def test_scheduler_tick_generates_only_for_snapshot_users(db_session) -> None:
    """매시 틱: PKG 스냅샷 보유 활성 유저만 생성, 스냅샷 없는 유저는 건너뛴다."""
    _create_user(db_session, 201)
    _seed_record(db_session, 201, [("systolic_bp", "150")])
    build_pkg_service(db_session).build_pkg(201)  # 스냅샷 영속(commit)

    _create_user(db_session, 202)  # 스냅샷 없음 → 대상 아님

    asyncio.run(run_daily_generation_tick())

    seoul_today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    repo = MissionRepository(db_session)
    assert len(repo.list_for_date(201, seoul_today)) >= 1
    assert repo.list_for_date(202, seoul_today) == []

    # 두 번째 틱은 멱등(claim 실패) → 중복 생성 없음
    n1 = len(repo.list_for_date(201, seoul_today))
    asyncio.run(run_daily_generation_tick())
    assert len(repo.list_for_date(201, seoul_today)) == n1


def test_get_today_missions_returns_generated(db_session) -> None:
    """GET /today 서비스: 로컬 오늘 배정된 미션을 payload 펼쳐 반환, 없으면 빈 목록."""
    _create_user(db_session, 301)
    _seed_record(db_session, 301, [("systolic_bp", "150")])
    today = local_date_for_timezone("Asia/Seoul")
    asyncio.run(
        MissionGenerationService(db_session).generate_for_user(301, today, source="scheduler")
    )

    items = MissionService(db_session).get_today_missions(301)
    assert len(items) >= 1
    assert items[0].title  # payload title 펼침
    assert items[0].status == "ASSIGNED"

    _create_user(db_session, 302)  # 미션 없음
    assert MissionService(db_session).get_today_missions(302) == []


def test_complete_mission_marks_completed_and_is_idempotent(db_session) -> None:
    """POST /complete 서비스: 본인 미션 완료(멱등), 없거나 남의 미션은 404."""
    from app.core.exceptions import NotFoundException

    _create_user(db_session, 401)
    _seed_record(db_session, 401, [("systolic_bp", "150")])
    today = local_date_for_timezone("Asia/Seoul")
    asyncio.run(
        MissionGenerationService(db_session).generate_for_user(401, today, source="scheduler")
    )
    repo = MissionRepository(db_session)
    mission_id = repo.list_for_date(401, today)[0].id

    svc = MissionService(db_session)
    svc.complete_mission(401, mission_id)
    done = repo.get_for_user(mission_id, 401)
    assert done is not None and done.status == "COMPLETED" and done.completed_at is not None

    # 멱등: 재요청해도 예외 없이 COMPLETED 유지
    svc.complete_mission(401, mission_id)
    again = repo.get_for_user(mission_id, 401)
    assert again is not None and again.status == "COMPLETED"

    # 남의 미션/없는 미션 → 404
    _create_user(db_session, 402)
    with pytest.raises(NotFoundException):
        svc.complete_mission(402, mission_id)
    with pytest.raises(NotFoundException):
        svc.complete_mission(401, 999999)


def test_build_history_reflects_past_completions(db_session) -> None:
    """완료 이력 → PKG.history(success_rate 14일창 + 최근 title). 생성 시 overlay 소스."""
    _create_user(db_session, 501)
    today = date(2026, 7, 3)
    past = today - timedelta(days=2)  # 만료(assigned_date < today)이면서 14일창 내
    repo = MissionRepository(db_session)
    for i in range(4):
        m = GeneratedMission(title=f"미션{i}", template_id=f"t{i}", mission_type="diet")
        row = repo.save_generated_mission(user_id=501, assigned_date=past, mission=m)
        if i == 0:
            row.status = "COMPLETED"  # 4건 중 1건 완료 → 0.25
    db_session.flush()

    history = repo.build_history(501, today=today)
    assert history.success_rate == 0.25
    assert len(history.recent_mission_titles) == 4
    assert "미션0" in history.recent_mission_titles


def test_generate_failure_records_failed_run(db_session, monkeypatch) -> None:
    """생성 실패 시 claim row가 살아남아 status='failed'·attempts 기록(관측·재시도 계약)."""

    async def _boom(*args, **kwargs):
        raise RuntimeError("pipeline blew up")

    monkeypatch.setattr(
        "app.domains.mission.generation_service.MissionPipeline.generate_missions", _boom
    )
    _create_user(db_session, 701)
    _seed_record(db_session, 701, [("systolic_bp", "150")])

    assert _gen(db_session, 701) is False
    db_session.expire_all()
    run = _gen_run(db_session, 701)
    assert run is not None  # rollback이 claim까지 지우지 않음
    assert run.status == "failed"
    assert run.error_code == "GENERATION_ERROR"
    assert run.attempts >= 1
    assert MissionRepository(db_session).list_for_date(701, _TODAY) == []


def test_checkup_regeneration_worker_runs_in_own_session(db_session) -> None:
    """오프로드 워커: 독립 세션(session_scope)에서 재생성이 도는지 검증."""
    from app.domains.health_metric.service import _run_checkup_regeneration

    _create_user(db_session, 801)
    _seed_record(db_session, 801, [("systolic_bp", "150")])
    build_pkg_service(db_session).build_pkg(801)  # 스냅샷 영속(commit)

    asyncio.run(_run_checkup_regeneration(801))

    today = local_date_for_timezone("Asia/Seoul")
    assert len(MissionRepository(db_session).list_for_date(801, today)) >= 1


def test_context_agent_carries_recent_mission_titles() -> None:
    """recent_mission_titles가 ContextAgent를 거쳐 컨텍스트로 전달되는지(엔진 소비)."""
    from app.domains.mission.agents.context_agent import ContextAgent
    from app.domains.mission.pkg import InMemoryPKG
    from app.domains.mission.schemas import PKG, History, PipelineConfig

    pkg = PKG(id="u1", history=History(recent_mission_titles=["미션A", "미션B"]))
    ctx = ContextAgent().build(InMemoryPKG(pkg), PipelineConfig())
    assert ctx.recent_mission_titles == ["미션A", "미션B"]


def test_regenerate_for_checkup_preserves_completed(db_session) -> None:
    """새 검진 재생성: 완료분은 보존, 미완료는 삭제 후 새 PKG로 재생성."""
    _create_user(db_session, 601)
    _seed_record(db_session, 601, [("systolic_bp", "150"), ("fasting_glucose", "130")])
    today = local_date_for_timezone("Asia/Seoul")
    gen = MissionGenerationService(db_session)
    asyncio.run(gen.generate_for_user(601, today, source="scheduler"))

    repo = MissionRepository(db_session)
    before = repo.list_for_date(601, today)
    assert len(before) >= 2
    completed_id = before[0].id
    before[0].status = "COMPLETED"
    db_session.commit()
    incomplete_ids = {m.id for m in before[1:]}  # 재생성 시 삭제 대상

    asyncio.run(gen.regenerate_for_checkup(601, today))

    after = repo.list_for_date(601, today)
    ids_after = {m.id for m in after}
    assert completed_id in ids_after  # 완료분 보존
    assert incomplete_ids.isdisjoint(ids_after)  # 옛 미완료분 삭제됨
    assert any(m.status == "ASSIGNED" for m in after)  # 새 생성분 존재
    run = _gen_run(db_session, 601)
    assert run is not None and run.status == "generated" and run.source == "event"
