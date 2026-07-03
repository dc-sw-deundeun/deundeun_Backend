"""미션 생성 서비스 — 멱등 생성, PKG 소비, user_missions 인스턴스 저장.

LLM 키를 제거해 결정적 fallback(mission_pool 템플릿)으로 돌린다 — 실 CLOVA 호출 방지.
DB 픽스처(db_session, Postgres testcontainers) 사용.
"""

import asyncio
from datetime import date

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.domains.mission.generation_service import MissionGenerationService
from app.domains.mission.models import MissionGenerationRun
from app.domains.mission.repository import MissionRepository
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
    return db.scalar(
        select(MissionGenerationRun).where(MissionGenerationRun.user_id == user_id)
    )


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
