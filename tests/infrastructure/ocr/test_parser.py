from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser


def _field(text, x_min, y_center, conf=0.95, y_height=0.0):
    return OcrFieldDTO(
        text=text,
        confidence=conf,
        x_min=x_min,
        x_max=x_min + 30,
        y_center=y_center,
        y_height=y_height,
    )


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


def test_row_clustering_uses_row_center_not_first_outlier_token():
    result = _result(
        [
            _field("01:10-1.9", 690, 307, y_height=15),
            _field("/15.6-16.5", 752, 306, y_height=13),
            _field("174.5", 425, 330, y_height=19),
            _field("cm", 525, 330, y_height=13),
            _field("신", 264, 331, y_height=17),
            _field("장", 283, 331, y_height=17),
        ]
    )

    metrics = {m.metric_code: m for m in OcrParser().parse(result)}

    assert metrics["height"].value == "174.5"


def test_label_header_can_use_next_row_values():
    result = _result(
        [
            _field("키", 10, 100),
            _field("및", 50, 100),
            _field("몸무게", 80, 100),
            _field("결과", 130, 100),
            _field("163.3", 10, 125),
            _field("/", 60, 125),
            _field("55.3", 90, 125),
        ]
    )

    metrics = {m.metric_code: m for m in OcrParser().parse(result)}

    assert metrics["height"].value == "163.3"
    assert metrics["weight"].value == "55.3"


def test_alt_can_use_second_number_from_previous_ast_row():
    result = _result(
        [
            _field("AST(SGOT)", 10, 100),
            _field("(IU/L)", 100, 100),
            _field("18", 160, 100),
            _field("9", 200, 100),
            _field("40이하", 240, 100),
            _field("35이하", 300, 100),
            _field("ALT(SGPT)", 10, 125),
            _field("(IU/L)", 100, 125),
        ]
    )

    metrics = {m.metric_code: m for m in OcrParser().parse(result)}

    assert metrics["ast"].value == "18"
    assert metrics["alt"].value == "9"


def test_parser_allows_single_character_ocr_typo_for_long_korean_labels():
    result = _result(
        [
            _field("히", 243, 385),
            _field("리", 264, 385),
            _field("둘", 285, 385),
            _field("레", 303, 385),
            _field("84.0", 429, 385),
            _field("cm", 525, 385),
            _field("체질랑지수", 243, 412),
            _field("24.1", 422, 412),
            _field("kg/m2", 505, 413),
        ]
    )

    metrics = {m.metric_code: m for m in OcrParser().parse(result)}

    assert metrics["waist"].value == "84.0"
    assert metrics["bmi"].value == "24.1"
