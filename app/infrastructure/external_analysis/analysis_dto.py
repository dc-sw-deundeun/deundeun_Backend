from pydantic import BaseModel, Field


class AnalysisSummaryDTO(BaseModel):
    risk_level: str
    summary_text: str
    positive_points: list[str] = Field(default_factory=list)
    caution_points: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    avoidances: list[str] = Field(default_factory=list)


class AnalysisMetricDTO(BaseModel):
    metric_code: str
    metric_name: str
    value: str
    unit: str | None = None
    status: str | None = None
    interpretation: str | None = None
    confidence: float | None = None


class MissionCandidateDTO(BaseModel):
    template_code: str
    priority: int = 1
    reason_code: str | None = None


class AnalysisCallbackDTO(BaseModel):
    external_job_id: str
    record_id: int
    status: str
    model_version: str | None = None
    summary: AnalysisSummaryDTO | None = None
    metrics: list[AnalysisMetricDTO] | None = None
    mission_candidates: list[MissionCandidateDTO] = Field(default_factory=list)


class AnalysisRequestDTO(BaseModel):
    record_id: int
    user_id: int
    metrics: list[AnalysisMetricDTO] = Field(default_factory=list)


class AnalysisJobResponseDTO(BaseModel):
    external_job_id: str
    status: str


class AnalysisStatusResponseDTO(BaseModel):
    external_job_id: str
    status: str


class AnalysisResultResponseDTO(BaseModel):
    external_job_id: str
    status: str
    summary: AnalysisSummaryDTO | None = None
    metrics: list[AnalysisMetricDTO] | None = None
    mission_candidates: list[MissionCandidateDTO] = Field(default_factory=list)
