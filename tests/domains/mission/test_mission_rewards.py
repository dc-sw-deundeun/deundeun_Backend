"""미션 생성 시 EXP(난이도 기반) + 예상 수행 시각(LLM 생성 + 규칙 폴백).

- xp_for_difficulty: 난이도→EXP(1→10/2→20/3→30).
- suggested_time: when 우선, 없으면 mission_type 기반 규칙(HH:MM).
- normalize_time: LLM이 준 시각이 형식 맞으면 채택, 아니면 규칙 폴백.
- build_seeds가 execution.time을 규칙값으로 채우고, _apply_phrase가 LLM 시각으로 덮되 폴백.
- save_generated_mission이 xp_reward를 난이도 기반으로 저장(DB).
"""

import re
from datetime import date

from app.domains.mission import policy
from app.domains.mission.agents.generator import Generator
from app.domains.mission.agents.params import build_seeds
from app.domains.mission.pkg import InMemoryPKG
from app.domains.mission.repository import MissionRepository
from app.domains.mission.schemas import PKG, Execution, GeneratedMission, MissionCandidate
from tests.domains.pkg.test_service import _create_user

_TIME_RE = r"^([01]\d|2[0-3]):[0-5]\d$"


# --- xp_for_difficulty ---


def test_xp_for_difficulty_scale() -> None:
    assert policy.xp_for_difficulty(1) == 10
    assert policy.xp_for_difficulty(2) == 20
    assert policy.xp_for_difficulty(3) == 30


def test_xp_for_difficulty_floor() -> None:
    assert policy.xp_for_difficulty(0) == 10  # 최소 1로 취급


# --- suggested_time (규칙) ---


def test_suggested_time_prefers_when() -> None:
    assert policy.suggested_time("exercise", "기상 후") == "07:00"
    assert policy.suggested_time("diet", "식후") == "13:00"
    assert policy.suggested_time("stress", "취침 전") == "22:00"


def test_suggested_time_by_type_when_no_when() -> None:
    assert policy.suggested_time("sleep", "") == "22:00"
    assert re.match(_TIME_RE, policy.suggested_time("hydration", ""))
    assert re.match(_TIME_RE, policy.suggested_time("unknown_type", ""))


# --- normalize_time (LLM 값 검증 + 폴백) ---


def test_normalize_time_accepts_valid_llm_time() -> None:
    assert policy.normalize_time("14:30", "exercise", "") == "14:30"


def test_normalize_time_falls_back_on_invalid() -> None:
    # 형식 오류·범위 초과·None → 규칙값
    assert policy.normalize_time("99:99", "sleep", "취침 전") == "22:00"
    assert policy.normalize_time("abc", "sleep", "취침 전") == "22:00"
    assert policy.normalize_time(None, "sleep", "취침 전") == "22:00"


# --- build_seeds가 규칙 time 세팅 ---


def test_build_seeds_sets_execution_time() -> None:
    pkg = PKG(id="u1", conditions=["hypertension"])
    seeds = build_seeds(InMemoryPKG(pkg), pkg, n=3)
    assert seeds  # 후보 존재
    for s in seeds:
        assert re.match(_TIME_RE, s.execution.time), f"{s.title}: time={s.execution.time!r}"


# --- execution.when 매핑 (M2: 모든 템플릿이 수행 시점을 가져야 함) ---


def test_every_template_defines_when() -> None:
    from app.domains.mission import pool

    missing = [t["id"] for t in pool.templates() if not t.get("when")]
    assert not missing, f"when 미정의 템플릿: {missing}"


def test_build_seeds_sets_execution_when() -> None:
    # 조건이 많은 페르소나로 여러 타입 템플릿이 seed로 뽑히게 한 뒤 when이 비지 않는지 확인.
    pkg = PKG(id="u1", conditions=["hypertension", "type2_diabetes", "obesity", "dyslipidemia"])
    seeds = build_seeds(InMemoryPKG(pkg), pkg, n=8)
    assert seeds
    for s in seeds:
        assert s.execution.when, f"{s.title}: when이 비어있음"


# --- _apply_phrase가 LLM time 적용 / 폴백 ---


def test_apply_phrase_uses_valid_llm_time() -> None:
    seed = MissionCandidate(
        title="식후 걷기", mission_type="exercise", execution=Execution(when="식후", time="13:00")
    )
    out = Generator()._apply_phrase(
        [seed], [{"index": 0, "rationale": "r", "grounded_on": [], "time": "14:30"}]
    )
    assert out[0].execution.time == "14:30"


def test_apply_phrase_falls_back_on_invalid_llm_time() -> None:
    seed = MissionCandidate(
        title="취침 준비", mission_type="sleep", execution=Execution(when="취침 전", time="22:00")
    )
    out = Generator()._apply_phrase(
        [seed], [{"index": 0, "rationale": "r", "grounded_on": [], "time": "25:99"}]
    )
    assert out[0].execution.time == "22:00"


# --- DB: save_generated_mission이 난이도 기반 xp 저장 ---


def test_save_generated_mission_sets_xp_from_difficulty(db_session) -> None:
    _create_user(db_session, 21)
    mission = GeneratedMission(
        title="식후 15분 걷기",
        mission_type="exercise",
        difficulty=2,
        execution=Execution(when="식후", duration_min=15, time="13:00"),
    )
    row = MissionRepository(db_session).save_generated_mission(
        user_id=21, assigned_date=date(2026, 7, 9), mission=mission
    )
    assert row.xp_reward == 20  # difficulty 2 → 20
    assert (row.payload or {})["execution"]["time"] == "13:00"  # 수행 시각 payload 보존
