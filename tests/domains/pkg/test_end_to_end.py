"""E2E: 검진 라벨 입력 → health_metric 룰검증 결과물 → PKG 생성 → 미션 생성 (각 스텝, 헤르메틱).

docs/pkg/sample_checkup.json = health_metric 평가 요청(라벨 기반). 실제 룰엔진
HealthMetricService.evaluate_metrics로 검증한 '결과물'(canonical_test_code+status)을 그대로
derive_from_evaluated로 PKG 조건에 반영한다 — "여기서 나온 결과물을 PKG로".
DB 없이(큐레이션 시드) 돌아가며, 스냅샷 영속(pkg_snapshots)은 test_persistence.py가 검증한다.
"""

import asyncio
import json
from pathlib import Path

from app.core.config import settings
from app.domains.health_metric.schemas import HealthMetricEvaluationRequest, HealthMetricInput
from app.domains.health_metric.service import HealthMetricService
from app.domains.mission import pool
from app.domains.mission.agents.base import LLMClient
from app.domains.mission.agents.pipeline import MissionPipeline
from app.domains.mission.pkg import InMemoryPKG
from app.domains.mission.schemas import PKG, PipelineConfig
from app.domains.pkg import graph
from app.domains.pkg.adapter import derive_from_evaluated

_FIXTURE = Path("docs/pkg/sample_checkup.json")


def _load() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def _evaluate(checkup: dict):
    """health_metric 룰엔진으로 라벨 입력을 검증 → 결과물(items)."""
    request = HealthMetricEvaluationRequest(
        sex=checkup.get("sex"),
        metrics=[HealthMetricInput(label=m["label"], value=m["value"]) for m in checkup["metrics"]],
    )
    return HealthMetricService().evaluate_metrics(request)


def test_step0_healthmetric_evaluate_produces_validated_result() -> None:
    items = _evaluate(_load())
    by_code = {it.canonical_test_code: it for it in items}
    # 라벨 → canonical_test_code + status(룰 판정). PKG는 이 결과물을 소비한다.
    assert by_code["FPG"].status == "risk"
    assert by_code["BP_SYS"].status == "risk"
    assert by_code["EGFR"].status == "risk"
    assert by_code["LDL"].status == "risk"


def test_step1_pkg_conditions_from_evaluated_result() -> None:
    items = _evaluate(_load())
    conditions, flags = derive_from_evaluated([it.model_dump() for it in items])
    assert conditions == [
        "hypertension",
        "type2_diabetes",
        "dyslipidemia",
        "obesity",
        "fatty_liver",
        "ckd",
    ]
    assert flags == {"cardiovascular_risk": True}


def _pkg_from_checkup() -> PKG:
    items = _evaluate(_load())
    conditions, flags = derive_from_evaluated([it.model_dump() for it in items])
    nodes, edges = graph.build_graph(conditions, graph.fallback_edge_specs(conditions))
    return PKG(id="user-1001", conditions=conditions, flags=flags, nodes=nodes, edges=edges)


def test_step2_pkg_graph_grounding_resolves() -> None:
    pkg = _pkg_from_checkup()
    client = InMemoryPKG(pkg)
    assert client.edge_exists("고혈압->심혈관질환")
    assert any(e.src == "hypertension" and e.dst == "cardiovascular_disease" for e in pkg.edges)
    assert pkg.medications == []


def test_step3_mission_generation_is_grounded_and_safe(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    pkg = _pkg_from_checkup()

    content = json.dumps(
        {
            "missions": [
                {
                    "title": "오늘 한 끼 저염식 하기",
                    "rationale": "고혈압·심혈관 관리",
                    "grounded_on": ["고혈압->심혈관질환"],
                    "execution": {"when": "저녁", "duration_min": None},
                    "difficulty": 2,
                    "mission_type": "diet",
                },
                {
                    "title": "물 8잔 마시기",  # ckd → 안전 게이트가 차단해야 함
                    "rationale": "수분",
                    "grounded_on": [],
                    "execution": {"when": "하루", "duration_min": None},
                    "difficulty": 1,
                    "mission_type": "hydration",
                },
            ]
        }
    )

    async def _call(self, payload):
        return {"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 10}}

    monkeypatch.setattr(LLMClient, "_call", _call)
    cfg = PipelineConfig(M3_kag=True, M4_verify_gate=True, M5_structured=True)
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    ms = asyncio.run(pipe.generate_missions(pkg, cfg, n=3))

    assert ms.persona_id == "user-1001"
    assert ms.missions
    assert all(not pool.check_mission(m, pkg) for m in ms.missions)
    assert "물 8잔 마시기" not in [m.title for m in ms.missions]  # ckd 금기 → 제외
    assert "물 8잔 마시기" in ms.meta.rejected


def test_ckd_triggers_referral_topic() -> None:
    pkg = _pkg_from_checkup()
    topics = [c for c, _t in pool.referral_topics(pkg)]
    assert "ckd" in topics  # 신장 기능 관련 병원 상담 권고
