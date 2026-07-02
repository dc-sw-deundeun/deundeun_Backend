"""검진 수치 → canonical 조건/플래그 도출 규칙 (순수 단위 테스트)."""

from app.domains.pkg.adapter import MetricReading, derive_conditions_and_flags


def _derive(pairs, **kw):
    return derive_conditions_and_flags(
        [MetricReading(metric_code=c, value=v) for c, v in pairs], **kw
    )


def test_empty_metrics_yield_nothing() -> None:
    assert _derive([]) == ([], {})


def test_unknown_metric_code_ignored() -> None:
    conditions, flags = _derive([("height", "170"), ("weight", "70")])
    assert conditions == []
    assert flags == {}


def test_fpg_caution_is_prediabetes_risk_is_diabetes() -> None:
    assert _derive([("fasting_glucose", "99")])[0] == []
    assert _derive([("fasting_glucose", "100")])[0] == ["prediabetes"]
    assert _derive([("fasting_glucose", "125")])[0] == ["prediabetes"]
    assert _derive([("fasting_glucose", "126")])[0] == ["type2_diabetes"]


def test_blood_pressure_risk_only_is_hypertension() -> None:
    assert _derive([("systolic_bp", "139")])[0] == []  # 주의(caution)는 조건 아님
    assert _derive([("systolic_bp", "140")])[0] == ["hypertension"]
    assert _derive([("diastolic_bp", "90")])[0] == ["hypertension"]


def test_lipids_egfr_bmi_thresholds() -> None:
    assert _derive([("ldl", "129")])[0] == []
    assert _derive([("ldl", "160")])[0] == ["dyslipidemia"]
    assert _derive([("total_cholesterol", "240")])[0] == ["dyslipidemia"]
    assert _derive([("egfr", "40")])[0] == ["ckd"]
    assert _derive([("bmi", "31")])[0] == ["obesity"]


def test_cardiovascular_risk_flag_when_two_components() -> None:
    conditions, flags = _derive([("systolic_bp", "150"), ("ldl", "170")])
    assert set(conditions) == {"hypertension", "dyslipidemia"}
    assert flags.get("cardiovascular_risk") is True


def test_single_component_no_cv_flag() -> None:
    _, flags = _derive([("systolic_bp", "150")])
    assert flags == {}


def test_high_risk_analysis_summary_sets_cv_flag() -> None:
    _, flags = _derive([("bmi", "31")], risk_level="HIGH_RISK")
    assert flags.get("cardiovascular_risk") is True


def test_conditions_are_deterministically_ordered() -> None:
    # 입력 순서와 무관하게 _CONDITION_ORDER를 따른다.
    conditions, _ = _derive([("ldl", "170"), ("fasting_glucose", "130"), ("systolic_bp", "150")])
    assert conditions == ["hypertension", "type2_diabetes", "dyslipidemia"]
