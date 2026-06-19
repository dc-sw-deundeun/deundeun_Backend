from pydantic import BaseModel


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
