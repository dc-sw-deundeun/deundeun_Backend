"""추세 기반 개인화 — compute_params N 조정 + ContextAgent/payload 흐름.

추세가 미션을 사람마다·상황마다 달라지게 만드는지 검증:
- 악화 추세 → 저위험 슬롯(count/cups/minutes)만 소폭 강화(+1).
- 운동 duration은 악화 추세로 자동 강화하지 않는다(안전).
- 저성공률 감산이 악화 강화보다 우선(안전).
- 추세가 컨텍스트/LLM payload까지 흐른다(설명이 궤적을 언급하도록).
"""

from app.domains.mission.agents.context_agent import ContextAgent
from app.domains.mission.agents.generator import Generator
from app.domains.mission.agents.params import compute_params
from app.domains.mission.pkg import InMemoryPKG
from app.domains.mission.schemas import (
    PKG,
    History,
    MetricTrend,
    PipelineConfig,
    Wearable,
)

_CUPS_TEMPLATE = {"id": "t_water", "type": "hydration", "slots": {"cups": {"base": 8}}}
_DURATION_TEMPLATE = {"id": "t_walk", "type": "exercise", "slots": {"duration": {"base": 20}}}


def _adverse_trend() -> MetricTrend:
    return MetricTrend(
        code="BP_SYS",
        label="수축기 혈압",
        direction="up",
        latest=140.0,
        previous=120.0,
        delta=20.0,
        points=2,
        adverse=True,
    )


def _pkg(*, trends=None, success_rate=None, flags=None) -> PKG:
    return PKG(
        id="user-1",
        conditions=["hypertension"],
        history=History(success_rate=success_rate),
        wearable=Wearable(),
        flags=flags or {},
        trends=trends or [],
    )


def test_adverse_trend_bumps_count_slot() -> None:
    pkg = _pkg(trends=[_adverse_trend()])
    params = compute_params(_CUPS_TEMPLATE, InMemoryPKG(pkg), pkg)
    assert params["cups"] == 9  # 8 + 1 (악화 추세)


def test_no_trend_leaves_count_slot_unchanged() -> None:
    pkg = _pkg(trends=[])
    params = compute_params(_CUPS_TEMPLATE, InMemoryPKG(pkg), pkg)
    assert params["cups"] == 8


def test_low_success_rate_takes_priority_over_adverse_bump() -> None:
    # 저성공률이면 강화(+1)하지 않고 오히려 줄인다(안전).
    pkg = _pkg(trends=[_adverse_trend()], success_rate=0.2)
    params = compute_params(_CUPS_TEMPLATE, InMemoryPKG(pkg), pkg)
    assert params["cups"] == max(int(8 * 0.7), 1)


def test_adverse_trend_does_not_escalate_exercise_duration() -> None:
    # 안전: 악화 추세가 운동 강도를 자동으로 올리면 안 됨.
    pkg = _pkg(trends=[_adverse_trend()])
    params = compute_params(_DURATION_TEMPLATE, InMemoryPKG(pkg), pkg)
    assert params["duration"] == 20


def test_context_agent_flows_trends() -> None:
    pkg = _pkg(trends=[_adverse_trend()])
    ctx = ContextAgent().build(InMemoryPKG(pkg), PipelineConfig())
    assert [t.code for t in ctx.trends] == ["BP_SYS"]


def test_ctx_payload_includes_trends() -> None:
    pkg = _pkg(trends=[_adverse_trend()])
    ctx = ContextAgent().build(InMemoryPKG(pkg), PipelineConfig())
    payload = Generator()._ctx_payload(ctx)
    assert "trends" in payload
    entry = payload["trends"][0]
    assert entry["direction"] == "up"
    assert entry["adverse"] is True
