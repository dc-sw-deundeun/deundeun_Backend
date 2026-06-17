from pydantic import BaseModel


class AnalysisSummaryDTO(BaseModel):
    # risk_level: str
    # summary_text: str
    # positive_points: list[str]
    # caution_points: list[str]
    # recommendations: list[str]
    # avoidances: list[str]
    pass


class AnalysisMetricDTO(BaseModel):
    # metric_code: str
    # metric_name: str
    # value: float
    # unit: str
    # status: str
    # interpretation: str
    pass


class AnalysisCallbackDTO(BaseModel):
    # external_job_id: str
    # status: str
    # summary: AnalysisSummaryDTO | None
    # metrics: list[AnalysisMetricDTO] | None
    pass
