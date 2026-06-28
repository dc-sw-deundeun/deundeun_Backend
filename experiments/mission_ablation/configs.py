"""실행할 ablation 조합."""

from app.domains.mission.schemas import PipelineConfig

COMBOS: dict[str, PipelineConfig] = {
    # 1. 베이스라인 — 전부 OFF (순수 LLM 자유 생성)
    "baseline": PipelineConfig(),
    # 2. 단일 모듈 — 개별 기여도
    "M1": PipelineConfig(M1_template=True),
    "M2": PipelineConfig(M2_graph_constrained=True),
    "M3": PipelineConfig(M3_kag=True),
    "M4": PipelineConfig(M4_verify_gate=True),
    "M5": PipelineConfig(M5_structured=True),
    # 3. 시점별 묶음
    "pre(M1+M3)": PipelineConfig(M1_template=True, M3_kag=True),
    "post(M2+M4)": PipelineConfig(M2_graph_constrained=True, M4_verify_gate=True),
    # 4. 추천 하이브리드
    "hybrid(M1+M4+M5)": PipelineConfig(
        M1_template=True, M4_verify_gate=True, M5_structured=True
    ),
    # 5. 풀스택 — 전부 ON
    "full": PipelineConfig(
        M1_template=True,
        M2_graph_constrained=True,
        M3_kag=True,
        M4_verify_gate=True,
        M5_structured=True,
    ),
}

# 단일 모듈 라벨(기여도 분석용)
SINGLE_MODULES = ["M1", "M2", "M3", "M4", "M5"]
