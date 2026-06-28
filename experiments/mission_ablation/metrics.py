"""평가 결과 모델."""

from pydantic import BaseModel, Field

from app.domains.mission.schemas import PipelineConfig


class EvalRecord(BaseModel):
    """페르소나 × config 한 셀의 평가 결과."""

    persona_id: str
    persona_kind: str = "normal"
    config_label: str
    config: PipelineConfig
    status: str = "generated"
    n_missions: int = 0

    # 안전
    safety_violations: int = 0
    safety_violation_rate: float = 0.0
    violation_reasons: list[str] = Field(default_factory=list)

    # 충실성(grounding)
    faithfulness: float = 0.0  # 인용 관계 중 PKG에 실재하는 비율(미설명 미션은 0)
    grounding_rate: float = 0.0  # ≥1개 유효 grounding을 가진 미션 비율

    # 적합성/완전성
    referral_satisfied: bool = True

    # 개인화 (G-Eval, 0~100)
    personalization: float = 0.0
    personalization_levels: dict[str, float] = Field(default_factory=dict)

    # 비용/지연
    latency_ms: float = 0.0
    total_tokens: int = 0
    llm_calls: int = 0
    regenerations: int = 0
