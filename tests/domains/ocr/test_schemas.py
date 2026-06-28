import pytest
from pydantic import ValidationError

from app.domains.ocr.schemas import OcrJobResponse
from app.domains.record.models import CheckupMetricResult
from app.domains.record.schemas import (
    CommitCheckupRequest,
    CommitCheckupResponse,
    MetricBulkUpdateRequest,
    MetricResponse,
    MetricUpdateItem,
    MetricUpdateRequest,
    MultiImageUploadRequest,
    UploadResponse,
    VerifyRequest,
)


def test_ocr_job_response_fields():
    response = OcrJobResponse(
        job_id=1,
        record_id=2,
        status="COMPLETED",
        parsed_field_count=9,
        error_message=None,
    )

    assert response.status == "COMPLETED"


def test_metric_response_low_confidence_flag():
    metric = CheckupMetricResult(
        id=3,
        record_id=2,
        metric_code="bmi",
        metric_name="체질량지수",
        value="24.1",
        unit="kg/m2",
        source="OCR",
        confidence=0.5,
        is_edited=False,
    )

    response = MetricResponse.from_model(metric, min_confidence=0.8)

    assert response.metric_id == 3
    assert response.low_confidence is True


def test_metric_response_manual_not_low_confidence():
    metric = CheckupMetricResult(
        id=4,
        record_id=2,
        metric_code="bmi",
        metric_name="체질량지수",
        value="25.0",
        unit="kg/m2",
        source="MANUAL",
        confidence=None,
        is_edited=True,
    )

    response = MetricResponse.from_model(metric, min_confidence=0.8)

    assert response.low_confidence is False


def test_record_request_schemas_parse_nested_metric_updates():
    update = MetricUpdateRequest(value="24.1")
    bulk = MetricBulkUpdateRequest(metrics=[{"metric_id": 3, "value": "24.1", "unit": "kg/m2"}])
    verify = VerifyRequest()
    multi_upload = MultiImageUploadRequest(images=["abc"])
    upload = UploadResponse(
        page_count=1,
        failed_pages=[],
        ocr_status="COMPLETED",
        metrics=[],
        content_hash="a" * 64,
    )
    commit_request = CommitCheckupRequest(
        ocr_status="COMPLETED",
        failed_pages=[],
        content_hash="b" * 64,
        metrics=[
            {
                "metric_code": "bmi",
                "metric_name": "체질량지수",
                "value": "24.1",
            }
        ],
    )
    commit_response = CommitCheckupResponse(
        record_id=2,
        verification_status="VERIFIED",
        metrics=[],
    )

    assert update.unit is None
    assert bulk.metrics[0].metric_id == 3
    assert verify.metrics is None
    assert multi_upload.images == ["abc"]
    assert upload.page_count == 1
    assert commit_request.metrics[0].metric_code == "bmi"
    assert commit_response.record_id == 2


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (MetricUpdateRequest, {"value": ""}),
        (MetricUpdateRequest, {"value": "1" * 51}),
        (MetricUpdateItem, {"metric_id": 3, "value": ""}),
        (MetricUpdateItem, {"metric_id": 3, "value": "1" * 51}),
    ],
)
def test_metric_update_rejects_invalid_value_length(schema, payload):
    with pytest.raises(ValidationError):
        schema(**payload)


@pytest.mark.parametrize("schema", [MetricUpdateRequest, MetricUpdateItem])
def test_metric_update_rejects_unit_longer_than_database_column(schema):
    payload = {"value": "24.1", "unit": "u" * 21}
    if schema is MetricUpdateItem:
        payload["metric_id"] = 3

    with pytest.raises(ValidationError):
        schema(**payload)


def test_commit_checkup_requires_sha256_content_hash():
    payload = {
        "ocr_status": "COMPLETED",
        "failed_pages": [],
        "metrics": [
            {
                "metric_code": "bmi",
                "metric_name": "체질량지수",
                "value": "24.1",
            }
        ],
    }

    with pytest.raises(ValidationError):
        CommitCheckupRequest(**payload)

    with pytest.raises(ValidationError):
        CommitCheckupRequest(**{**payload, "content_hash": "g" * 64})
