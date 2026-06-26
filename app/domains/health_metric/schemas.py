import math

from pydantic import BaseModel, Field, field_validator


class HealthMetricReferenceResponse(BaseModel):
    # metric_code: str
    # metric_name: str
    # description: str
    # reference_min: float | None
    # reference_max: float | None
    # unit: str
    pass


class MetricDetailResponse(BaseModel):
    # metric_code: str
    # value: float
    # status: str
    # interpretation: str
    # reference: HealthMetricReferenceResponse
    # analysis_summary: str | None
    pass


_ALLOWED_SEX_VALUES = {"male", "female", "남", "여", "남성", "여성", "m", "f"}


class HealthMetricInput(BaseModel):
    label: str = Field(..., max_length=200, description="OCR 또는 클라이언트가 전달한 항목명")
    value: float = Field(..., description="검진 수치")
    unit: str | None = Field(default=None, max_length=20, description="선택 입력 단위")
    item9_positive: bool | None = Field(default=None, description="PHQ-9 9번 문항 양성 여부")

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("value must be a finite number")
        return v


class HealthMetricEvaluationRequest(BaseModel):
    sex: str | None = Field(default=None, description="male/female 또는 남/여")
    measured_at: str | None = Field(default=None, description="검진 결과지 날짜 YYYY-MM-DD")
    metrics: list[HealthMetricInput] = Field(..., min_length=1, max_length=100)

    @field_validator("sex")
    @classmethod
    def sex_must_be_allowed(cls, v: str | None) -> str | None:
        if v is not None and v.lower() not in _ALLOWED_SEX_VALUES:
            raise ValueError(f"sex must be one of {sorted(_ALLOWED_SEX_VALUES)}")
        return v


class HealthMetricEvaluationItem(BaseModel):
    input_label: str
    canonical_test_code: str | None
    name: str | None
    value: float
    unit: str | None = None
    status: str
    status_label: str
    matched_rule: str | None = None
    note: str | None = None


class HealthMetricItemExplanation(BaseModel):
    canonical_test_code: str | None
    input_label: str
    title: str
    explanation: str
    status_label: str


class HealthMetricExplanation(BaseModel):
    status: str
    summary: str
    highlights: list[str]
    item_explanations: list[HealthMetricItemExplanation]
    disclaimer: str


class HealthMetricRangeSegment(BaseModel):
    label: str
    from_value: float
    to_value: float
    color: str


class HealthMetricRangeBar(BaseModel):
    min: float
    max: float
    marker: float
    marker_percent: float
    segments: list[HealthMetricRangeSegment]


class HealthMetricSummaryCard(BaseModel):
    code: str | None
    label: str
    value: float
    unit: str | None
    status: str
    status_label: str
    value_text: str
    badge_text: str
    range_bar: HealthMetricRangeBar | None = None


class HealthMetricOverallSummary(BaseModel):
    title: str
    summary: str
    counts: dict[str, int]


class HealthMetricSummaryView(BaseModel):
    analysis_id: int | None = None
    overall: HealthMetricOverallSummary
    cards: list[HealthMetricSummaryCard]


class HealthMetricTrendPoint(BaseModel):
    label: str
    value: float


class HealthMetricTrend(BaseModel):
    title: str
    points: list[HealthMetricTrendPoint]


class HealthMetricMeaning(BaseModel):
    title: str
    body: str


class HealthMetricRecommendations(BaseModel):
    title: str
    items: list[str]


class HealthMetricDetailView(BaseModel):
    analysis_id: int | None = None
    metric: HealthMetricSummaryCard
    range_bar: HealthMetricRangeBar | None = None
    trend: HealthMetricTrend
    meaning: HealthMetricMeaning
    recommendations: HealthMetricRecommendations


class HealthMetricAnalysisCreateResponse(BaseModel):
    analysis_id: int
    summary: HealthMetricSummaryView


class HealthMetricEvaluationResponse(BaseModel):
    results: list[HealthMetricEvaluationItem]
    explanation: HealthMetricExplanation
    ui: dict | None = None
