from pydantic import BaseModel, Field

from app.domains.health_metric.schemas import HealthMetricEvaluationItem

# ---------------------------------------------------------------------------
# 라우터/영속화용 placeholder (Phase B에서 확정)
# ---------------------------------------------------------------------------


class TodayMissionsResponse(BaseModel):
    pass


class MissionCompleteRequest(BaseModel):
    pass


class WeeklyStatisticsResponse(BaseModel):
    pass


# ---------------------------------------------------------------------------
# 미션 생성 멀티에이전트 엔진 I/O
# ---------------------------------------------------------------------------

# 미션 타입 — 생활습관 범주만 허용한다. 약물/처방 관련 타입은 의도적으로 제외한다.
MISSION_TYPES = (
    "diet",  # 식단
    "exercise",  # 운동
    "hydration",  # 수분
    "sleep",  # 수면
    "stress",  # 스트레스/정신건강
    "checkup_followup",  # 재검·추적 권유
    "habit",  # 기록 등 습관
)

# 완료 방식 — manual: 사용자가 직접 완료, record: 기록 업로드로 자동 완료, auto: 시스템 자동
COMPLETION_TYPES = ("manual", "record", "auto")


class KnowledgeFact(BaseModel):
    """KG(외부 의학 KG ⨝ 개인 PKG)에서 가져온 미션 근거.

    PKG/KG 미구축 단계에서는 StubKnowledgeProvider가 빈 리스트를 반환하므로,
    엔진은 근거 없이도 동작한다. 실제 연동 시 finding별 권장행동·금기로 채워진다.
    """

    finding_code: str | None = None
    finding_name: str | None = None
    recommendations: list[str] = Field(default_factory=list)  # 권장 생활습관 행동
    cautions: list[str] = Field(default_factory=list)  # 금기/주의 (DUR·식품·연령)
    source: str = "kg"


class MissionGenerationContext(BaseModel):
    """엔진 입력 — 검진 판정결과 + 프로필 + 게임상태 + KG 근거를 조립한 컨텍스트."""

    user_id: int
    sex: str | None = None
    age: int | None = None
    findings: list[HealthMetricEvaluationItem] = Field(default_factory=list)
    character_level: int = 1
    recent_mission_titles: list[str] = Field(default_factory=list)  # 반복 회피용
    recent_completion_rate: float | None = None  # 0.0~1.0, 난이도 조절용
    knowledge: list[KnowledgeFact] = Field(default_factory=list)
    target_date: str | None = None  # YYYY-MM-DD
    max_missions: int = 4


class MissionCandidate(BaseModel):
    """Drafter가 만든 후보 미션 (안전 검증·선택 전)."""

    title: str
    description: str
    mission_type: str
    completion_type: str = "manual"
    target_finding_code: str | None = None
    rationale: str = ""


class SafetyVerdict(BaseModel):
    """Safety Validator의 후보별 판정."""

    title: str
    approved: bool
    reason: str = ""
    revised_title: str | None = None
    revised_description: str | None = None


class GeneratedMission(BaseModel):
    """최종 생성 미션 (경험치 배정 완료)."""

    title: str
    description: str
    mission_type: str
    completion_type: str
    exp_reward: int
    target_finding_code: str | None = None
    rationale: str = ""
    source: str = "generated"  # generated | fallback


class MissionSet(BaseModel):
    """엔진 출력."""

    status: str  # generated | partial | fallback
    missions: list[GeneratedMission]
    disclaimer: str
    target_date: str | None = None
