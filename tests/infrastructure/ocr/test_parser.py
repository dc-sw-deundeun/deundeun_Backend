from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser


def _field(text, x_min, y_center, conf=0.95):
    return OcrFieldDTO(text=text, confidence=conf, x_min=x_min, x_max=x_min + 30, y_center=y_center)


def _result(fields):
    return OcrResultDTO(fields=fields)


def test_parses_simple_numeric_value():
    result = _result(
        [
            _field("공복혈당", 10, 100),
            _field("109", 120, 100),
            _field("100 미만", 300, 100),  # 참조범위 — 무시돼야 함
        ]
    )
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}
    assert metrics["fasting_glucose"].value == "109"
    assert metrics["fasting_glucose"].unit == "mg/dL"


def test_parses_decimal_value():
    result = _result([_field("체질량지수", 10, 200), _field("24.1", 120, 200)])
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}
    assert metrics["bmi"].value == "24.1"


def test_splits_blood_pressure():
    result = _result(
        [
            _field("혈압", 10, 300),
            _field("110", 120, 300),
            _field("/", 160, 300),
            _field("70", 190, 300),
        ]
    )
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}
    assert metrics["systolic_bp"].value == "110"
    assert metrics["diastolic_bp"].value == "70"


def test_parses_categorical_urine_protein():
    result = _result([_field("요단백", 10, 400), _field("음성(-)", 120, 400)])
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}
    assert metrics["urine_protein"].value == "음성"


def test_missing_value_is_omitted():
    result = _result([_field("공복혈당", 10, 500)])  # 값 토큰 없음
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}
    assert "fasting_glucose" not in metrics


def test_confidence_is_carried():
    result = _result(
        [
            _field("혈색소", 10, 600, conf=0.9),
            _field("16.6", 120, 600, conf=0.8),
        ]
    )
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}
    assert metrics["hemoglobin"].confidence == 0.8  # 값 토큰 신뢰도
