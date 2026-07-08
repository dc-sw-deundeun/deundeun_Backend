"""저위험 타입(habit·stress) 자유생성 라우팅·안전·폴백 (#47).

프로덕션(M1 ON)에서 안전 필수 타입은 템플릿을 유지하고, habit·stress만 LLM이 카테고리
안에서 자유생성하는지 검증한다. 실제 문구 품질은 staging 수동 확인 영역이므로, 여기서는
라우팅/타입강제/안전게이트/폴백을 결정적으로 본다.
"""

import asyncio

from app.core.config import settings
from app.domains.mission import pool
from app.domains.mission.agents.base import LLMClient, Usage
from app.domains.mission.agents.pipeline import MissionPipeline
from app.domains.mission.schemas import PKG, PipelineConfig


def _dep_persona() -> PKG:
    # depression_screen → seed 슬레이트에 stress(breathing_stretch)가 들어온다
    return PKG(id="dep", conditions=["depression_screen"])


def _cvd_dep_persona() -> PKG:
    return PKG(id="cvd", kind="trap", conditions=["cardiovascular_disease", "depression_screen"])


def _fake_structured(free_type_response):
    """phrase 호출(rationales)과 free 호출(missions)을 schema_name으로 분기하는 목."""

    async def _structured(self, system, user, schema, schema_name):
        if schema_name == "rationales":
            items = [
                {"index": i, "rationale": "이유", "grounded_on": []}
                for i in range(len(user.get("missions", [])))
            ]
            return {"items": items}, Usage(calls=1)
        if schema_name == "missions":
            missions = [free_type_response(cat) for cat in user.get("categories", [])]
            return {"missions": missions}, Usage(calls=1)
        return {}, Usage()

    return _structured


def _free_mission(title, mtype):
    return {
        "title": title,
        "rationale": "이유",
        "grounded_on": [],
        "execution": {"when": "", "duration_min": None},
        "difficulty": 1,
        "mission_type": mtype,
    }


def test_free_eligible_types_are_marked() -> None:
    assert "habit" in pool.FREE_ELIGIBLE_TYPES
    assert "stress" in pool.FREE_ELIGIBLE_TYPES
    # 안전 필수 타입은 자유 대상이 아니다
    assert "exercise" not in pool.FREE_ELIGIBLE_TYPES
    assert "diet" not in pool.FREE_ELIGIBLE_TYPES


def test_low_risk_slot_is_freely_generated_others_stay_template(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    # stress 카테고리는 LLM 자유 문구, 나머지는 템플릿 유지
    monkeypatch.setattr(
        LLMClient,
        "structured",
        _fake_structured(lambda cat: _free_mission(f"자유-{cat}", cat)),
    )
    cfg = PipelineConfig(M1_template=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(_dep_persona(), cfg, n=3))

    titles = [m.title for m in ms.missions]
    # stress 슬롯 = 자유생성 문구
    assert any(t == "자유-stress" for t in titles)
    # sleep 슬롯 = 템플릿 문구 유지(자유생성 아님)
    assert any("잠자리에 들기" in t for t in titles)


def test_free_generated_type_is_forced_to_requested_category(monkeypatch) -> None:
    """LLM이 카테고리를 오라벨(exercise)해도 요청한 stress로 강제되어야 한다(게이트 회피 방지)."""
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(
        LLMClient,
        "structured",
        _fake_structured(lambda cat: _free_mission("스트레스 풀기 산책", "exercise")),
    )
    cfg = PipelineConfig(M1_template=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(_dep_persona(), cfg, n=3))

    free = next((m for m in ms.missions if m.title == "스트레스 풀기 산책"), None)
    assert free is not None
    assert free.mission_type == "stress"  # exercise가 아니라 요청 카테고리로 강제


def test_free_generated_unsafe_mission_is_gated(monkeypatch) -> None:
    """자유생성분도 M4 안전 게이트를 그대로 탄다 — 위험 키워드는 출력에 남지 않는다."""
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(
        LLMClient,
        "structured",
        _fake_structured(lambda cat: _free_mission("고강도 달리기로 스트레스 풀기", cat)),
    )
    cfg = PipelineConfig(M1_template=True, M4_verify_gate=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    persona = _cvd_dep_persona()  # 심혈관질환 → 고강도 운동 금지
    ms = asyncio.run(pipe.generate_missions(persona, cfg, n=3))

    assert "고강도 달리기로 스트레스 풀기" not in [m.title for m in ms.missions]
    assert [m for m in ms.missions if pool.check_mission(m, persona)] == []


def test_free_slot_falls_back_to_template_without_llm(monkeypatch) -> None:
    """LLM 없으면 자유 슬롯도 템플릿으로 degrade — 크래시 없이."""
    monkeypatch.setattr(settings, "openai_api_key", None)
    cfg = PipelineConfig(M1_template=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key=None))  # has_llm False
    ms = asyncio.run(pipe.generate_missions(_dep_persona(), cfg, n=3))

    assert ms.status == "fallback"
    assert ms.missions
    # 자유 대상 stress 슬롯도 템플릿 문구(심호흡·스트레칭)로 채워짐
    assert any("심호흡" in m.title for m in ms.missions)
