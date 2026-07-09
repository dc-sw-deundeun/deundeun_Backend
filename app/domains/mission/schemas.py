from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# 라우터/영속화용 placeholder (프로덕션 엔드포인트, 추후 확정)
# ---------------------------------------------------------------------------


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
    age: int | None = Field(default=None, ge=0, le=130)
    sex: str | None = None


class Wearable(BaseModel):
    steps_avg: int | None = Field(default=None, ge=0)
    resting_hr: int | None = Field(default=None, ge=0)
    sleep_hours_avg: float | None = Field(default=None, ge=0)


class History(BaseModel):
    success_rate: float | None = Field(default=None, ge=0.0, le=1.0)  # 과거 미션 완료율
    recent_mission_titles: list[str] = Field(default_factory=list)


class MetricTrend(BaseModel):
    """검진 지표의 시점 간 변화(궤적) — 같은 조건이라도 사람마다 달라지는 개인화 축.

    direction은 원시 수치의 방향(up/down/flat), adverse는 그 방향이 건강에 불리한지
    (지표 극성 적용: 혈압·혈당·BMI·LDL 등은 상승이, HDL·eGFR·혈색소는 하락이 불리).
    """

    code: str  # canonical 지표코드 (BP_SYS, FPG, BMI ...)
    label: str = ""  # 한국어 표시명 (수축기 혈압 ...)
    direction: Literal["up", "down", "flat"] = "flat"
    latest: float | None = None
    previous: float | None = None
    delta: float | None = None  # latest - previous
    points: int = 0  # 관측 횟수
    adverse: bool = False  # 이 방향이 건강에 불리한가


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
    trends: list[MetricTrend] = Field(default_factory=list)  # 검진 지표 궤적(개인화)
    curated_facts: list[str] = Field(default_factory=list)  # 외부 KG 이웃을 정제한 임상 요약
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
    trends: list[MetricTrend] = Field(default_factory=list)  # 검진 지표 궤적(개인화)
    curated_facts: list[str] = Field(default_factory=list)  # 외부 KG 정제 임상 요약
    success_rate: float | None = None
    recent_mission_titles: list[str] = Field(default_factory=list)  # 최근 배정분(반복 회피용)


class Execution(BaseModel):
    when: str = ""  # "식후" 등
    duration_min: int | None = Field(default=None, ge=0)
    time: str = ""  # 예상 수행 시각 "HH:MM"(알람용) — 규칙 기본값 후 LLM이 덮음


class MissionCandidate(BaseModel):
    title: str
    rationale: str = ""
    grounded_on: list[str] = Field(default_factory=list)
    execution: Execution = Field(default_factory=Execution)
    difficulty: int = Field(default=1, ge=1)
    mission_type: str = ""
    template_id: str | None = None


class GeneratedMission(BaseModel):
    title: str
    rationale: str = ""
    grounded_on: list[str] = Field(default_factory=list)
    execution: Execution = Field(default_factory=Execution)
    difficulty: int = Field(default=1, ge=1)
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


# ---------------------------------------------------------------------------
# 라우터 응답 뷰 (user_missions 인스턴스 → 프론트 표시)
# ---------------------------------------------------------------------------


class TodayMissionItem(BaseModel):
    """오늘의 미션 1건 — 템플릿 기반(#24 기본미션) + 엔진 생성분을 모두 표현.

    공통 필드는 항상 채워지고, 출처별 필드(엔진 vs 레거시 템플릿)는 없는 쪽이 기본값/None.
    """

    mission_id: int
    template_code: str | None = None
    title: str = ""
    status: Literal["ASSIGNED", "COMPLETED"] = "ASSIGNED"
    assigned_date: date
    xp_reward: int
    completed_at: datetime | None = None
    source_record_id: int | None = None
    # 엔진 생성 미션(payload 기반) 필드
    rationale: str = ""
    mission_type: str = ""
    difficulty: int = 1
    execution: Execution = Field(default_factory=Execution)
    grounded_on: list[str] = Field(default_factory=list)
    source: str = "generated"
    # 레거시 DB 템플릿(#24 기본미션) 필드 — 엔진 생성분은 None
    description: str | None = None
    category: str | None = None
    verification_mode: str | None = None


class TodayMissionsResponse(BaseModel):
    date: date
    total: int
    completed: int
    items: list[TodayMissionItem]
