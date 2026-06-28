"""실행할 ablation 조합 + 적응형(라우팅) 구조.

COMBOS는 정적 PipelineConfig. ROUTERS는 페르소나에 따라 config를 고르는 함수
(FrugalGPT식 모듈 캐스케이드) — 비용·과제약을 줄이면서 안전을 유지하는 신규 구조.
"""

from collections.abc import Callable

from app.domains.mission import pool
from app.domains.mission.schemas import PKG, PipelineConfig

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
    # 생성 전 전체(게이트 없음) — 게이트 세금 없이 개인화/근거만
    "gen_only(M1+M3+M5)": PipelineConfig(M1_template=True, M3_kag=True, M5_structured=True),
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


def _risk_routed(pkg: PKG) -> PipelineConfig:
    """위험군(PKG에 금기/권고/위험플래그)만 full 게이트, 정상군은 생성 전만(게이트 세금 회피)."""
    if pool.has_active_constraints(pkg):
        return PipelineConfig(
            M1_template=True, M2_graph_constrained=True, M3_kag=True,
            M4_verify_gate=True, M5_structured=True,
        )
    return PipelineConfig(M1_template=True, M3_kag=True, M5_structured=True)


def _adaptive(pkg: PKG) -> PipelineConfig:
    """더 잘게: M1·M5 항상, M3는 KG 관계가 있을 때만, M2·M4는 위험군만."""
    risk = pool.has_active_constraints(pkg)
    return PipelineConfig(
        M1_template=True,
        M3_kag=bool(pkg.edges),
        M5_structured=True,
        M2_graph_constrained=risk,
        M4_verify_gate=risk,
    )


# 적응형(라우팅) 구조 — 페르소나별 config 선택
ROUTERS: dict[str, Callable[[PKG], PipelineConfig]] = {
    "risk_routed": _risk_routed,
    "adaptive": _adaptive,
}
