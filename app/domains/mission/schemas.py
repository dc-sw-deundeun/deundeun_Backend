from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 라우터/영속화용 placeholder (프로덕션 엔드포인트, 추후 확정)
# ---------------------------------------------------------------------------


class TodayMissionsResponse(BaseModel):
    pass


class MissionCompleteRequest(BaseModel):
    pass


class WeeklyStatisticsResponse(BaseModel):
    pass


# ---------------------------------------------------------------------------
# 공통 상수
# ---------------------------------------------------------------------------

# 미션 타입 — 생활습관 범주만. 약물/처방 관련 타입은 의도적으로 제외.
MISSION_TYPES = (
    "diet",
    "exercise",
    "hydration",
    "sleep",
    "stress",
    "checkup_followup",
    "habit",
)
COMPLETION_TYPES = ("manual", "record", "auto")


# ---------------------------------------------------------------------------
# PKG (개인 지식 그래프) 입력 모델 — 실험에서는 페르소나 목 데이터로 채운다.
# ---------------------------------------------------------------------------


class PkgNode(BaseModel):
    id: str
    label: str = ""  # 한국어 표시명
    type: str = ""  # Disease | Drug | Effect | Lifestyle | Metric ...


class PkgEdge(BaseModel):
    src: str
    rel: str  # disease_disease | drug_effect | CORRELATES_WITH ...
    dst: str
    attrs: dict = Field(default_factory=dict)  # {"delta": -12, "risk": "high"}


class Demographics(BaseModel):
    age: int | None = None
    sex: str | None = None


class Wearable(BaseModel):
    steps_avg: int | None = None
    resting_hr: int | None = None
    sleep_hours_avg: float | None = None


class History(BaseModel):
    success_rate: float | None = None  # 0.0~1.0, 과거 미션 완료율
    recent_mission_titles: list[str] = Field(default_factory=list)


class GroundTruth(BaseModel):
    """평가용 정답 — 페르소나별로 사전 정의."""

    ideal: list[str] = Field(default_factory=list)  # 이상적 미션 개념(루브릭)
    forbidden: list[str] = Field(default_factory=list)  # 절대 나오면 안 되는 미션
    required_referrals: list[str] = Field(default_factory=list)  # 강제 권고 항목
    expected_grounding: list[str] = Field(default_factory=list)  # 좋은 미션이 인용할 엣지
    notes: str = ""


class PKG(BaseModel):
    """한 사람의 개인 지식 그래프 (실험 입력 단위)."""

    id: str
    name: str = ""
    kind: str = "normal"  # normal | trap
    demographics: Demographics = Field(default_factory=Demographics)
    conditions: list[str] = Field(default_factory=list)  # canonical condition id
    medications: list[str] = Field(default_factory=list)  # canonical drug id
    wearable: Wearable = Field(default_factory=Wearable)
    history: History = Field(default_factory=History)
    nodes: list[PkgNode] = Field(default_factory=list)
    edges: list[PkgEdge] = Field(default_factory=list)
    flags: dict[str, bool] = Field(default_factory=dict)  # cardiovascular_risk 등
    ground_truth: GroundTruth | None = None


# ---------------------------------------------------------------------------
# 파이프라인 설정 (M1~M5 ablation 토글)
# ---------------------------------------------------------------------------


class PipelineConfig(BaseModel):
    M1_template: bool = False  # 파라미터 계산 단계: 강도를 룰로 산출(슬롯 주입)
    M2_graph_constrained: bool = False  # 검증: grounded_on ↔ PKG 엣지 대조
    M3_kag: bool = False  # 컨텍스트: KG 멀티홉 관계 주입
    M4_verify_gate: bool = False  # 검증: hard-constraint 안전 게이트 + 재생성
    M5_structured: bool = False  # 생성: JSON 스키마 강제

    def label(self) -> str:
        on = [m for m, v in self.model_dump().items() if v]
        return "baseline" if not on else "+".join(sorted(on))


# ---------------------------------------------------------------------------
# 엔진 중간/출력 모델
# ---------------------------------------------------------------------------


class Relation(BaseModel):
    """M3가 추출한 관계 체인 (사람이 읽을 수 있는 형태 + 원본 엣지)."""

    text: str  # "고혈압 -[disease_disease]-> 심혈관질환(고위험)"
    edge: str  # "hypertension->cardiovascular_disease" (id 기반 canonical)
    cite: str = ""  # "고혈압->심혈관질환" (라벨 기반, grounded_on에 그대로 복사하도록 제공)


class StructuredContext(BaseModel):
    """Agent 1 출력 — 생성에 들어갈 정리된 컨텍스트."""

    conditions: list[str] = Field(default_factory=list)  # 표시명
    medications: list[str] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)  # M3 ON일 때만 채워짐
    wearable: Wearable = Field(default_factory=Wearable)
    success_rate: float | None = None


class Execution(BaseModel):
    when: str = ""  # "식후" 등
    duration_min: int | None = None


class MissionCandidate(BaseModel):
    title: str
    rationale: str = ""
    grounded_on: list[str] = Field(default_factory=list)
    execution: Execution = Field(default_factory=Execution)
    difficulty: int = 1
    mission_type: str = ""
    template_id: str | None = None


class GeneratedMission(BaseModel):
    title: str
    rationale: str = ""
    grounded_on: list[str] = Field(default_factory=list)
    execution: Execution = Field(default_factory=Execution)
    difficulty: int = 1
    mission_type: str = ""
    template_id: str | None = None
    source: str = "generated"  # generated | fallback


class SafetyVerdict(BaseModel):
    title: str
    approved: bool
    reason: str = ""
    revised_title: str | None = None


class GenerationMeta(BaseModel):
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    regenerations: int = 0
    rejected: list[str] = Field(default_factory=list)  # 안전게이트가 막은 미션


class MissionSet(BaseModel):
    persona_id: str = ""
    config: PipelineConfig = Field(default_factory=PipelineConfig)
    status: str = "generated"  # generated | partial | fallback
    missions: list[GeneratedMission] = Field(default_factory=list)
    disclaimer: str = ""
    meta: GenerationMeta = Field(default_factory=GenerationMeta)
