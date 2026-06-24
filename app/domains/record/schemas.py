from pydantic import BaseModel, Field


class MetricResponse(BaseModel):
    metric_id: int
    metric_code: str
    metric_name: str
    value: str | None
    unit: str | None
    status: str | None
    confidence: float | None
    low_confidence: bool
    source: str
    is_edited: bool

    @classmethod
    def from_model(cls, metric, min_confidence: float) -> "MetricResponse":
        low_confidence = metric.confidence is not None and metric.confidence < min_confidence
        return cls(
            metric_id=metric.id,
            metric_code=metric.metric_code,
            metric_name=metric.metric_name,
            value=metric.value,
            unit=metric.unit,
            status=metric.status,
            confidence=metric.confidence,
            low_confidence=low_confidence,
            source=metric.source,
            is_edited=metric.is_edited,
        )


class MultiImageUploadRequest(BaseModel):
    images: list[str] = Field(min_length=1, max_length=10)


class UploadResponse(BaseModel):
    record_id: int
    page_count: int
    failed_pages: list[int]
    ocr_status: str
    metrics: list["MetricResponse"]


class MetricUpdateRequest(BaseModel):
    value: str = Field(min_length=1, max_length=50)
    unit: str | None = Field(default=None, max_length=20)


class MetricUpdateItem(BaseModel):
    metric_id: int
    value: str = Field(min_length=1, max_length=50)
    unit: str | None = Field(default=None, max_length=20)


class MetricBulkUpdateRequest(BaseModel):
    metrics: list[MetricUpdateItem]


class VerifyRequest(BaseModel):
    metrics: list[MetricUpdateItem] | None = None
