from app.infrastructure.ocr.metric_dictionary import (
    METRIC_SPECS,
    find_best_alias_match,
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


def test_find_best_alias_match_bmi_with_spaces():
    result = find_best_alias_match("체 질 량 지 수")
    assert result is not None
    spec, alias = result
    assert spec.code == "bmi"
    assert alias == "체질량지수"


def test_find_best_alias_match_unknown_returns_none():
    assert find_best_alias_match("발급번호") is None


def test_blood_pressure_is_bp_pair():
    result = find_best_alias_match("혈압")
    assert result is not None
    assert result[0].kind == "bp_pair"


def test_urine_protein_is_categorical():
    result = find_best_alias_match("요단백")
    assert result is not None
    spec, _ = result
    assert spec.kind == "categorical"
    assert "음성" in spec.categories


def test_height_is_hw_pair():
    result = find_best_alias_match("키")
    assert result is not None
    assert result[0].code == "height"
    assert result[0].kind == "hw_pair"


def test_shinjangjilhwan_does_not_match_height():
    # "신장"(2자 exact) != "신장질환" → height alias에 매칭되면 안 됨
    result = find_best_alias_match("신장질환")
    assert result is None or result[0].code != "height"


def test_longest_alias_wins_creatinine_over_height():
    # "크레아티닌(mg/dL)": "크레아티닌"(5자) > "신장"(2자 exact, 불일치) → creatinine
    result = find_best_alias_match("크레아티닌(mg/dL)")
    assert result is not None
    assert result[0].code == "creatinine"


def test_substring_alias_in_compound_token():
    # "혈청크레아티닌(mg/dL)"에서 "크레아티닌"(5자) substring 매칭
    result = find_best_alias_match("혈청크레아티닌(mg/dL)")
    assert result is not None
    assert result[0].code == "creatinine"


def test_vldl_does_not_match_ldl():
    # LDL is 3-char exact match only — VLDL contains LDL but must not match
    result = find_best_alias_match("VLDL")
    assert result is None or result[0].code != "ldl"


def test_egfr_case_insensitive():
    # normalize_label uppercases, so egfr/EGFR/eGFR all match
    for token in ("eGFR", "EGFR", "egfr"):
        result = find_best_alias_match(token)
        assert result is not None, f"{token!r} should match egfr spec"
        assert result[0].code == "egfr", f"{token!r} matched {result[0].code} instead of egfr"


def test_gokhyeolap_alias_matches_blood_pressure():
    # '고혈압' 행에서 수축기/이완기 혈압 값을 잡을 수 있어야 함
    result = find_best_alias_match("고혈압")
    assert result is not None
    spec, _ = result
    assert spec.code == "blood_pressure"
    assert spec.kind == "bp_pair"


def test_unit_suffix_stripped_before_matching():
    # '허리들례(cm)' → strip → '허리들례' → alias '허리둘레'와 ≤2자 typo → waist
    result = find_best_alias_match("허리들례(cm)")
    assert result is not None
    assert result[0].code == "waist"


def test_two_char_ocr_typo_matches_bmi():
    # '제질랑지수' — 체→제(1), 량→랑(1) — ≤2자 허용
    result = find_best_alias_match("제질랑지수")
    assert result is not None
    assert result[0].code == "bmi"


def test_one_char_typo_fasting_glucose_with_unit():
    # '공복혈담(mg/dL)' → strip → '공복혈담' → alias '공복혈당' 1자 typo
    result = find_best_alias_match("공복혈담(mg/dL)")
    assert result is not None
    assert result[0].code == "fasting_glucose"


def test_gokhyeolap_jeondan_does_not_match():
    # '고혈압전단계' (6자) 는 어떤 alias와도 일치하지 않아야 함
    result = find_best_alias_match("고혈압전단계")
    assert result is None or result[0].code not in {"blood_pressure", "systolic_bp", "diastolic_bp"}
