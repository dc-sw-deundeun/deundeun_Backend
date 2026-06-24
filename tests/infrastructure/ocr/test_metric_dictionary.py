from app.infrastructure.ocr.metric_dictionary import (
    METRIC_SPECS,
    find_spec_by_label,
    normalize_label,
)


def test_covers_core_metrics():
    codes = {s.code for s in METRIC_SPECS}
    for required in {
        "bmi",
        "systolic_bp",
        "diastolic_bp",
        "fasting_glucose",
        "hemoglobin",
        "ast",
        "alt",
        "gamma_gtp",
        "creatinine",
        "egfr",
        "urine_protein",
        "total_cholesterol",
        "hdl",
        "ldl",
        "triglyceride",
        "height",
        "weight",
        "waist",
    }:
        assert required in codes


def test_normalize_label_strips_spaces():
    assert normalize_label("체 질 량 지 수") == "체질량지수"


def test_find_spec_by_label_matches_alias_with_spaces():
    spec = find_spec_by_label("체 질 량 지 수")
    assert spec is not None
    assert spec.code == "bmi"


def test_find_spec_by_label_unknown_returns_none():
    assert find_spec_by_label("발급번호") is None


def test_blood_pressure_is_bp_pair():
    spec = find_spec_by_label("혈압")
    assert spec.kind == "bp_pair"


def test_urine_protein_is_categorical():
    spec = find_spec_by_label("요단백")
    assert spec.kind == "categorical"
    assert "음성" in spec.categories
