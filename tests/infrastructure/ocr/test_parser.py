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


def test_parsed_metric_has_page_index():
    from app.infrastructure.ocr.parser import ParsedMetric

    m = ParsedMetric(
        metric_code="X", metric_name="X", value="1", unit="", confidence=0.9, raw_text="1"
    )
    assert m.page_index == 0  # default

    m2 = ParsedMetric(
        metric_code="X",
        metric_name="X",
        value="1",
        unit="",
        confidence=0.9,
        raw_text="1",
        page_index=3,
    )
    assert m2.page_index == 3


def test_shinjangjilhwan_alias_collision_resolved():
    # "신장질환"이 height alias "신장"에 exact 매칭되지 않아야 함
    # "크레아티닌(mg/dL)"이 creatinine(5자)으로 선택돼 0.9가 올바르게 추출돼야 함
    result = _result(
        [
            _field("신장질환", 10, 100),
            _field("크레아티닌(mg/dL)", 100, 100),
            _field("0.9", 300, 100),
            _field("1.5이하", 380, 100),
        ]
    )
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}
    assert "height" not in metrics
    assert metrics["creatinine"].value == "0.9"


def test_parses_height_weight_pair():
    result = _result(
        [
            _field("키", 10, 200),
            _field("(cm)", 50, 200),
            _field("및", 80, 200),
            _field("몸무게", 110, 200),
            _field("(kg)", 160, 200),
            _field("163.3", 210, 200),
            _field("/", 260, 200),
            _field("55.3", 290, 200),
        ]
    )
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}
    assert metrics["height"].value == "163.3"
    assert metrics["weight"].value == "55.3"


def test_character_split_label_joined_by_window():
    # Clova가 "체질량지수"를 글자별로 분리해 반환한 경우
    result = _result(
        [
            _field("체", 10, 300),
            _field("질", 20, 300),
            _field("량", 30, 300),
            _field("지", 40, 300),
            _field("수", 50, 300),
            _field("20.7", 120, 300),
        ]
    )
    metrics = {m.metric_code: m for m in OcrParser().parse(result)}
    assert metrics["bmi"].value == "20.7"
