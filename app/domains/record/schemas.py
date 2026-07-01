from datetime import datetime

from pydantic import BaseModel, Field


class MetricResponse(BaseModel):
    metric_id: int
    metric_code: str
    metric_name: str
    value: str | None
    unit: str | None
    status: str | None
    reference_min: float | None = None
    reference_max: float | None = None
    confidence: float | None
    low_confidence: bool
    source: str
    is_edited: bool

    @classmethod
    def from_model(
        cls,
        metric,
        min_confidence: float,
        *,
        reference_min: float | None = None,
        reference_max: float | None = None,
        status: str | None = None,
    ) -> "MetricResponse":
        low_confidence = metric.confidence is not None and metric.confidence < min_confidence
        return cls(
            metric_id=metric.id,
            metric_code=metric.metric_code,
            metric_name=metric.metric_name,
            value=metric.value,
            unit=metric.unit,
            status=status if status is not None else metric.status,
            reference_min=reference_min if reference_min is not None else metric.reference_min,
            reference_max=reference_max if reference_max is not None else metric.reference_max,
            confidence=metric.confidence,
            low_confidence=low_confidence,
            source=metric.source,
            is_edited=metric.is_edited,
        )


class PreviewMetricResponse(BaseModel):
    metric_code: str
    metric_name: str
    value: str | None
    unit: str | None
    confidence: float | None
    raw_text: str | None
    page_index: int | None
    low_confidence: bool
    out_of_range: bool

    @classmethod
    def from_parsed(cls, metric, min_confidence: float) -> "PreviewMetricResponse":
        low_confidence = metric.confidence is not None and metric.confidence < min_confidence
        return cls(
            metric_code=metric.metric_code,
            metric_name=metric.metric_name,
            value=metric.value,
            unit=metric.unit,
            confidence=metric.confidence,
            raw_text=metric.raw_text,
            page_index=metric.page_index,
            low_confidence=low_confidence,
            out_of_range=metric.out_of_range,
        )


class MultiImageUploadRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"images": ["<base64 또는 data:image/jpeg;base64,...>"]}}}

    images: list[str] = Field(min_length=1, max_length=10)


class UploadResponse(BaseModel):
    page_count: int
    failed_pages: list[int]
    ocr_status: str
    content_hash: str
    metrics: list[PreviewMetricResponse]


class CommitMetricRequest(BaseModel):
    metric_code: str = Field(min_length=1, max_length=50)
    metric_name: str = Field(min_length=1, max_length=100)
    value: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, max_length=20)
    confidence: float | None = None
    raw_text: str | None = Field(default=None, max_length=200)
    page_index: int | None = None
    is_edited: bool = False


class CommitCheckupRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "ocr_status": "COMPLETED",
                "failed_pages": [],
                "content_hash": "a3f1e2d4b5c6a7e8f9012345678901234567890123456789012345678901234",
                "metrics": [
                    {
                        "metric_code": "fasting_glucose",
                        "metric_name": "공복혈당",
                        "value": "95",
                        "unit": "mg/dL",
                        "confidence": 0.97,
                        "raw_text": "공복혈당 95",
                        "page_index": 0,
                        "is_edited": False,
                    },
                    {
                        "metric_code": "bmi",
                        "metric_name": "체질량지수",
                        "value": "22.5",
                        "unit": "kg/m²",
                        "confidence": 0.95,
                        "raw_text": "BMI 22.5",
                        "page_index": 0,
                        "is_edited": False,
                    },
                ],
            }
        }
    }

    ocr_status: str = Field(pattern=r"^(COMPLETED|PARTIAL|FAILED)$")
    failed_pages: list[int] = Field(default_factory=list)
    metrics: list[CommitMetricRequest] = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ManualCheckupRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "measured_at": "2026-06-01T09:00:00Z",
                "metrics": [
                    {
                        "metric_code": "fasting_glucose",
                        "metric_name": "공복혈당",
                        "value": "100",
                        "unit": "mg/dL",
                        "confidence": None,
                        "raw_text": None,
                        "page_index": None,
                        "is_edited": False,
                    },
                    {
                        "metric_code": "total_cholesterol",
                        "metric_name": "총콜레스테롤",
                        "value": "190",
                        "unit": "mg/dL",
                        "confidence": None,
                        "raw_text": None,
                        "page_index": None,
                        "is_edited": False,
                    },
                ],
            }
        }
    }

    measured_at: datetime | None = None
    metrics: list[CommitMetricRequest] = Field(min_length=1)


class CommitCheckupResponse(BaseModel):
    record_id: int
    verification_status: str
    metrics: list[MetricResponse]


class CheckupListItem(BaseModel):
    record_id: int
    source_type: str
    verification_status: str
    analysis_status: str | None
    ocr_status: str | None
    measured_at: datetime | None
    created_at: datetime
    metric_count: int


class CheckupListResponse(BaseModel):
    items: list[CheckupListItem]
    page: int
    size: int
    total: int


class CheckupDetailResponse(BaseModel):
    record_id: int
    source_type: str
    verification_status: str
    analysis_status: str | None
    ocr_status: str | None
    measured_at: datetime | None
    verified_at: datetime | None
    created_at: datetime
    overall_status: str
    metrics: list[MetricResponse]


class TrendPoint(BaseModel):
    record_id: int
    date: str
    value: str
    unit: str | None


class MetricTrendSeries(BaseModel):
    metric_code: str
    metric_name: str
    points: list[TrendPoint]


class CheckupTrendsResponse(BaseModel):
    record_id: int
    trends: list[MetricTrendSeries]


class MetricUpdateRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {"value": "98", "unit": "mg/dL"}}}

    value: str = Field(min_length=1, max_length=50)
    unit: str | None = Field(default=None, max_length=20)


class MetricUpdateItem(BaseModel):
    metric_id: int
    value: str = Field(min_length=1, max_length=50)
    unit: str | None = Field(default=None, max_length=20)


class MetricBulkUpdateRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "metrics": [
                    {"metric_id": 1, "value": "98", "unit": "mg/dL"},
                    {"metric_id": 2, "value": "22.5", "unit": "kg/m²"},
                ]
            }
        }
    }

    metrics: list[MetricUpdateItem]


class VerifyRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "metrics": [
                    {"metric_id": 1, "value": "98", "unit": "mg/dL"},
                ]
            }
        }
    }

    metrics: list[MetricUpdateItem] | None = None
