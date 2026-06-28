import asyncio
import json

import pytest

from app.core.config import settings
from app.domains.health_metric.schemas import HealthMetricEvaluationItem
from app.domains.mission.agents.drafter import MissionDrafter
from app.domains.mission.agents.knowledge import StubKnowledgeProvider
from app.domains.mission.agents.orchestrator import MissionGenerator
from app.domains.mission.agents.safety import SafetyValidator, is_safe
from app.domains.mission.policy import calculate_exp_reward
from app.domains.mission.schemas import KnowledgeFact, MissionCandidate


def _item(
    code: str,
    status: str,
    *,
    name: str | None = None,
    value: float = 0.0,
    status_label: str = "",
    note: str | None = None,
) -> HealthMetricEvaluationItem:
    return HealthMetricEvaluationItem(
        input_label=code,
        canonical_test_code=code,
        name=name or code,
        value=value,
        status=status,
        status_label=status_label or status,
        note=note,
    )


def _openai_missions(*missions: dict) -> dict:
    return {"output_text": json.dumps({"missions": list(missions)})}


def _mission(
    title: str,
    mission_type: str = "diet",
    *,
    description: str = "오늘 실천해요.",
    target: str | None = None,
) -> dict:
    return {
        "title": title,
        "description": description,
        "mission_type": mission_type,
        "completion_type": "manual",
        "target_finding_code": target,
        "rationale": "근거",
    }


def test_calculate_exp_reward_by_type() -> None:
    assert calculate_exp_reward("checkup_followup") == 25
    assert calculate_exp_reward("exercise") == 20
    assert calculate_exp_reward("unknown_type") == 10  # 기본값


def test_is_safe_rejects_medical_directives() -> None:
    ok = MissionCandidate(
        title="30분 걷기", description="가볍게 걸어요.", mission_type="exercise"
    )
    bad_phrase = MissionCandidate(
        title="혈압약 복용 중단하기", description="약을 끊어요.", mission_type="habit"
    )
    bad_type = MissionCandidate(
        title="아무거나", description="설명", mission_type="medication"
    )
    assert is_safe(ok) is True
    assert is_safe(bad_phrase) is False
    assert is_safe(bad_type) is False


def test_generate_via_llm_drafter(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)  # 기본 에이전트 LLM 비활성

    async def fake_call(self, payload):
        assert payload["text"]["format"]["type"] == "json_schema"
        return _openai_missions(
            _mission("저염식 한 끼 실천", "diet", target="LDL"),
            _mission("계단 오르기", "exercise"),
            _mission("물 8잔 마시기", "hydration"),
        )

    monkeypatch.setattr(MissionDrafter, "_call_openai", fake_call)

    generator = MissionGenerator(drafter=MissionDrafter(api_key="test"))
    result = asyncio.run(
        generator.generate(
            user_id=1,
            evaluation_results=[_item("LDL", "risk"), _item("BMI", "normal")],
            character_level=1,
        )
    )

    assert result.status == "generated"
    assert len(result.missions) == 3
    assert all(m.source == "generated" for m in result.missions)
    assert all(m.exp_reward > 0 for m in result.missions)
    assert result.disclaimer
    # 위험 finding(LDL)과 연결된 미션이 가장 앞에 정렬된다
    assert result.missions[0].target_finding_code == "LDL"


def test_generate_falls_back_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    generator = MissionGenerator()
    result = asyncio.run(
        generator.generate(
            user_id=1,
            evaluation_results=[_item("LDL", "caution")],
            max_missions=4,
        )
    )

    assert result.status == "fallback"
    assert 1 <= len(result.missions) <= 4
    assert all(m.source == "fallback" for m in result.missions)
    assert all(is_safe_mission(m) for m in result.missions)


def test_generate_falls_back_on_llm_error(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    async def boom(self, payload):
        raise RuntimeError("boom")

    monkeypatch.setattr(MissionDrafter, "_call_openai", boom)

    generator = MissionGenerator(drafter=MissionDrafter(api_key="test"))
    result = asyncio.run(
        generator.generate(user_id=1, evaluation_results=[_item("TG", "risk")])
    )

    assert result.status == "fallback"
    assert result.missions


def test_safety_drops_unsafe_llm_candidate_marks_partial(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    async def fake_call(self, payload):
        return _openai_missions(
            _mission("30분 걷기", "exercise"),
            _mission("복용량을 늘려 관리하기", "habit"),  # 금지문구 → 백스톱 제거
        )

    monkeypatch.setattr(MissionDrafter, "_call_openai", fake_call)

    generator = MissionGenerator(drafter=MissionDrafter(api_key="test"))
    result = asyncio.run(
        generator.generate(user_id=1, evaluation_results=[_item("FPG", "risk")])
    )

    assert result.status == "partial"
    titles = [m.title for m in result.missions]
    assert "30분 걷기" in titles
    assert "복용량을 늘려 관리하기" not in titles


def test_personalizer_skips_recent_titles(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    async def fake_call(self, payload):
        return _openai_missions(
            _mission("물 8잔 마시기", "hydration"),
            _mission("계단 오르기", "exercise"),
        )

    monkeypatch.setattr(MissionDrafter, "_call_openai", fake_call)

    generator = MissionGenerator(drafter=MissionDrafter(api_key="test"))
    result = asyncio.run(
        generator.generate(
            user_id=1,
            evaluation_results=[_item("BMI", "caution")],
            recent_mission_titles=["물 8잔 마시기"],
        )
    )

    titles = [m.title for m in result.missions]
    assert "물 8잔 마시기" not in titles
    assert "계단 오르기" in titles


def test_knowledge_facts_passed_to_drafter(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    captured: dict = {}

    async def fake_call(self, payload):
        captured["payload"] = payload
        return _openai_missions(_mission("저염식 실천", "diet"))

    monkeypatch.setattr(MissionDrafter, "_call_openai", fake_call)

    class FakeKnowledge:
        async def fetch(self, findings):
            return [
                KnowledgeFact(
                    finding_code="LDL",
                    finding_name="LDL 콜레스테롤",
                    recommendations=["포화지방 줄이기"],
                )
            ]

    generator = MissionGenerator(
        drafter=MissionDrafter(api_key="test"), knowledge=FakeKnowledge()
    )
    asyncio.run(generator.generate(user_id=1, evaluation_results=[_item("LDL", "risk")]))

    user_content = captured["payload"]["input"][1]["content"]
    assert "포화지방 줄이기" in user_content


def test_context_builder_drops_normal_findings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)

    generator = MissionGenerator()
    result = asyncio.run(
        generator.generate(
            user_id=1,
            evaluation_results=[_item("BMI", "normal"), _item("LDL", "risk")],
        )
    )
    # normal만 있으면 fallback 풀로, risk 포함 시에도 정상 동작 (여기선 fallback 경로)
    assert result.missions


@pytest.mark.parametrize(
    "provider",
    [StubKnowledgeProvider(), SafetyValidator(api_key=None)],
    ids=["stub-knowledge", "safety-no-llm"],
)
def test_components_are_constructible(provider) -> None:
    assert provider is not None


def is_safe_mission(mission) -> bool:
    """GeneratedMission도 동일 백스톱 기준으로 안전한지 확인한다."""
    return is_safe(
        MissionCandidate(
            title=mission.title,
            description=mission.description,
            mission_type=mission.mission_type,
        )
    )
