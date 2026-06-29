import asyncio
import json

import pytest

from app.core.config import settings
from app.domains.mission import pool
from app.domains.mission.agents.base import LLMClient
from app.domains.mission.agents.pipeline import MissionPipeline
from app.domains.mission.schemas import PKG, GeneratedMission, PipelineConfig, PkgEdge, PkgNode

# ---------------------------------------------------------------------------
# 페르소나 헬퍼
# ---------------------------------------------------------------------------


def _ckd_trap() -> PKG:
    return PKG(
        id="ckd",
        kind="trap",
        conditions=["ckd", "hypertension"],
        flags={"cardiovascular_risk": True},
        nodes=[
            PkgNode(id="hypertension", label="고혈압"),
            PkgNode(id="cardiovascular_disease", label="심혈관질환"),
        ],
        edges=[
            PkgEdge(
                src="hypertension",
                rel="disease_disease",
                dst="cardiovascular_disease",
                attrs={"risk": "high"},
            )
        ],
    )


def _warfarin_trap() -> PKG:
    return PKG(id="warf", kind="trap", conditions=["dyslipidemia"], medications=["warfarin"])


def _edema_trap() -> PKG:
    return PKG(id="edema", kind="trap", conditions=["ankle_edema", "obesity"])


def _exercise_prohibited_trap() -> PKG:
    return PKG(
        id="noex", kind="trap", conditions=["hypertension"], flags={"exercise_prohibited": True}
    )


# ---------------------------------------------------------------------------
# OpenAI 호환 chat/completions 응답 목
# ---------------------------------------------------------------------------

_USAGE = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


def _chat_call(content: str):
    async def _call(self, payload):
        return {"choices": [{"message": {"content": content}}], "usage": _USAGE}

    return _call


def _missions_json(*missions: dict) -> str:
    return json.dumps({"missions": list(missions)})


def _m(title, mtype="diet", rationale="이유", grounded=None, duration=None):
    return {
        "title": title,
        "rationale": rationale,
        "grounded_on": grounded or [],
        "execution": {"when": "", "duration_min": duration},
        "difficulty": 1,
        "mission_type": mtype,
    }


# ---------------------------------------------------------------------------
# 테스트
# ---------------------------------------------------------------------------


def test_fallback_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    pipe = MissionPipeline(llm=LLMClient(api_key=None))
    ms = asyncio.run(pipe.generate_missions(_ckd_trap(), PipelineConfig(), n=3))
    assert ms.status == "fallback"
    assert ms.missions
    assert all(not pool.check_mission(m, _ckd_trap()) for m in ms.missions)


def test_full_structured_generation(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    content = _missions_json(
        _m("저염식 한 끼", "diet", grounded=["고혈압->심혈관질환"]),
        _m("식후 10분 걷기", "exercise"),
        _m("자정 전 취침", "sleep"),
    )
    monkeypatch.setattr(LLMClient, "_call", _chat_call(content))
    cfg = PipelineConfig(M3_kag=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(_ckd_trap(), cfg, n=3))

    assert ms.status == "generated"
    assert len(ms.missions) == 3
    assert ms.missions[0].grounded_on == ["고혈압->심혈관질환"]
    assert ms.meta.total_tokens == 150
    assert ms.meta.llm_calls == 1


def test_M4_blocks_trap_and_regenerates(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    content = _missions_json(_m("물 8잔 마시기", "hydration"), _m("저염식 한 끼", "diet"))
    monkeypatch.setattr(LLMClient, "_call", _chat_call(content))
    cfg = PipelineConfig(M4_verify_gate=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(_ckd_trap(), cfg, n=3))

    titles = [m.title for m in ms.missions]
    assert "물 8잔 마시기" not in titles
    assert ms.meta.regenerations > 0
    assert any(r == "물 8잔 마시기" for r in ms.meta.rejected)
    assert any(m.mission_type == "checkup_followup" for m in ms.missions)


def test_M2_rejects_hallucinated_grounding(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    content = _missions_json(
        _m("저염식 한 끼", "diet", grounded=["당뇨->암"]),  # 존재하지 않음 → reject
        _m("자정 전 취침", "sleep", grounded=["고혈압->심혈관질환"]),  # 존재 → ok
    )
    monkeypatch.setattr(LLMClient, "_call", _chat_call(content))
    cfg = PipelineConfig(M2_graph_constrained=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(_ckd_trap(), cfg, n=3))

    titles = [m.title for m in ms.missions]
    assert "저염식 한 끼" not in titles
    assert "자정 전 취침" in titles


def test_M1_numbers_come_from_rules_not_llm(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    content = json.dumps({"items": [{"index": 0, "rationale": "이유", "grounded_on": []}]})
    monkeypatch.setattr(LLMClient, "_call", _chat_call(content))
    persona = PKG(id="p", conditions=["type2_diabetes"], wearable={"steps_avg": 8000})
    cfg = PipelineConfig(M1_template=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(persona, cfg, n=1))

    walk = next((m for m in ms.missions if m.template_id == "walk_after_meal"), None)
    assert walk is not None
    assert "30분" in walk.title  # 룰 계산값(base10 + steps>6000 → +20)
    assert walk.execution.duration_min == 30
    assert walk.rationale == "이유"


def test_M5_off_free_text_parsing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    free = (
        "제목: 저염식 한 끼\n이유: 혈압 관리\n근거: 고혈압->심혈관질환\n\n"
        "제목: 자정 전 취침\n이유: 수면 관리\n근거: \n"
    )
    monkeypatch.setattr(LLMClient, "_call", _chat_call(free))
    cfg = PipelineConfig()  # M5 OFF
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(_ckd_trap(), cfg, n=2))

    titles = [m.title for m in ms.missions]
    assert "저염식 한 끼" in titles
    assert ms.missions[0].grounded_on == ["고혈압->심혈관질환"]


@pytest.mark.parametrize(
    ("persona", "forbidden"),
    [
        (_ckd_trap(), _m("물 8잔 마시기", "hydration")),
        (_warfarin_trap(), _m("시금치 듬뿍 먹기", "diet")),
        (_edema_trap(), _m("1시간 걷기", "exercise")),
        (_exercise_prohibited_trap(), _m("식후 30분 걷기", "exercise")),
    ],
    ids=["ckd", "warfarin", "edema", "no-exercise"],
)
def test_trap_safety_zero_with_M4(monkeypatch, persona, forbidden) -> None:
    """M4 ON이면 함정 페르소나의 금지 미션이 절대 출력에 남지 않는다."""
    monkeypatch.setattr(settings, "openai_api_key", None)
    content = _missions_json(forbidden, _m("저염식 한 끼", "diet"), _m("심호흡 10분", "stress"))
    monkeypatch.setattr(LLMClient, "_call", _chat_call(content))
    cfg = PipelineConfig(M4_verify_gate=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(persona, cfg, n=3))

    assert [m for m in ms.missions if pool.check_mission(m, persona)] == []


def test_llm_failure_is_marked_fallback_not_generated(monkeypatch) -> None:
    """LLM 호출이 실패하면 status/source가 generated가 아니라 fallback이어야 한다(CodeRabbit #3)."""
    monkeypatch.setattr(settings, "openai_api_key", None)

    async def boom(self, payload):
        raise RuntimeError("api down")

    monkeypatch.setattr(LLMClient, "_call", boom)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(_ckd_trap(), PipelineConfig(M1_template=True), n=3))

    assert ms.status == "fallback"
    assert ms.missions
    assert all(m.source == "fallback" for m in ms.missions)


def test_extract_json_handles_code_fences() -> None:
    from app.domains.mission.agents.base import _extract_json

    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('설명...\n{"a": 2}\n끝') == {"a": 2}


def test_check_mission_direct() -> None:
    assert pool.check_mission(
        GeneratedMission(title="물 8잔 마시기", mission_type="hydration"), _ckd_trap()
    )
    assert not pool.check_mission(
        GeneratedMission(title="저염식 한 끼", mission_type="diet"), _ckd_trap()
    )


def test_schema_rejects_out_of_range_boundary_values() -> None:
    """경계 모델 수치 범위를 스키마에서 고정한다(CodeRabbit)."""
    from pydantic import ValidationError

    from app.domains.mission.schemas import Execution, History, Wearable

    with pytest.raises(ValidationError):
        History(success_rate=1.5)
    with pytest.raises(ValidationError):
        Wearable(steps_avg=-1)
    with pytest.raises(ValidationError):
        Execution(duration_min=-5)
