"""계약 테스트: PKG 조립 결과가 미션 생성 엔진(#17)에 그대로 소비되는지.

검진 수치 → adapter → graph 조립으로 PKG를 만들고(= PkgService 내부 조립과 동일, DB 불필요),
MissionPipeline(M1+M3+M5)에 넣어 grounded·safe 미션이 나오는지, grounded_on 엣지가
PKG로 검증되는지 확인한다. (LLM은 stub — tests/domains/mission/test_pipeline.py 패턴 재사용)
"""

import asyncio
import json

from app.core.config import settings
from app.domains.mission import pool
from app.domains.mission.agents.base import LLMClient
from app.domains.mission.agents.pipeline import MissionPipeline
from app.domains.mission.pkg import InMemoryPKG
from app.domains.mission.schemas import PKG, PipelineConfig
from app.domains.pkg import graph
from app.domains.pkg.adapter import MetricReading, derive_conditions_and_flags

_USAGE = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


def _chat_call(content: str):
    async def _call(self, payload):
        return {"choices": [{"message": {"content": content}}], "usage": _USAGE}

    return _call


def _assemble(pairs) -> PKG:
    conditions, flags = derive_conditions_and_flags(
        [MetricReading(metric_code=c, value=v) for c, v in pairs]
    )
    specs = graph.fallback_edge_specs(conditions)
    nodes, edges = graph.build_graph(conditions, specs)
    return PKG(id="user-1", conditions=conditions, flags=flags, nodes=nodes, edges=edges)


def test_assembled_pkg_produces_grounded_missions(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    pkg = _assemble([("systolic_bp", "150"), ("fasting_glucose", "130")])
    assert "hypertension" in pkg.conditions

    # 엔진이 만든 grounded_on이 PKG 엣지로 검증되는지 (M3가 만든 cite 형식)
    client = InMemoryPKG(pkg)
    assert client.edge_exists("고혈압->심혈관질환")

    content = json.dumps(
        {
            "missions": [
                {
                    "title": "오늘 한 끼 저염식 하기",
                    "rationale": "혈압 관리",
                    "grounded_on": ["고혈압->심혈관질환"],
                    "execution": {"when": "저녁", "duration_min": None},
                    "difficulty": 1,
                    "mission_type": "diet",
                }
            ]
        }
    )
    monkeypatch.setattr(LLMClient, "_call", _chat_call(content))
    pipe = MissionPipeline(llm=LLMClient(api_key="test"))
    cfg = PipelineConfig(M1_template=True, M3_kag=True, M5_structured=True)
    ms = asyncio.run(pipe.generate_missions(pkg, cfg, n=3))

    assert ms.persona_id == "user-1"
    assert ms.missions
    # 안전: 생성된 미션 중 hard-constraint 위반 없음
    assert all(not pool.check_mission(m, pkg) for m in ms.missions)


def test_ckd_pkg_blocks_hydration_missions() -> None:
    # egfr 위험 → ckd 도출 → 물 많이 마시기류가 안전 게이트에서 걸리는지
    pkg = _assemble([("egfr", "40")])
    assert "ckd" in pkg.conditions
    from app.domains.mission.schemas import GeneratedMission

    unsafe = GeneratedMission(title="물 8잔 마시기", mission_type="hydration")
    assert pool.check_mission(unsafe, pkg)  # 위반 사유 있음(차단)
