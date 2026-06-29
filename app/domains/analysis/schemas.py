from pydantic import BaseModel, Field


class AnalysisJobCreateResponse(BaseModel):
    job_id: int
    record_id: int
    status: str
    external_job_id: str


class AnalysisJobStatusResponse(BaseModel):
    job_id: int
    record_id: int
    status: str
    external_job_id: str
    attempt_count: int
    error_code: str | None = None
    model_version: str | None = None


class MissionCandidateResponse(BaseModel):
    template_code: str | None = None
    priority: int | None = None
    reason_code: str | None = None
    title: str | None = None
    description: str | None = None


class AnalysisSummaryResponse(BaseModel):
    record_id: int
    summary_text: str
    risk_level: str
    positive_points: list[str] = Field(default_factory=list)
    caution_points: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    avoidances: list[str] = Field(default_factory=list)
    model_version: str | None = None
    mission_candidates: list[MissionCandidateResponse] = Field(default_factory=list)


class AnalysisResultResponse(BaseModel):
    job_id: int
    record_id: int
    status: str
    summary: AnalysisSummaryResponse | None = None


class AnalysisCallbackRequest(BaseModel):
    external_job_id: str
    record_id: int
    status: str
    model_version: str | None = None
    summary: dict | None = None
    metrics: list[dict] | None = None
    mission_candidates: list[dict] = Field(default_factory=list)
