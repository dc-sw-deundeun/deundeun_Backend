"""검진 판정 → 미션 엔진 canonical 조건/플래그 도출 (순수 함수).

미션 엔진(app/domains/mission)이 소비하는 PKG의 `conditions`/`flags`를 검진 판정에서 결정한다.
판정(status)은 health_metric의 룰엔진(`METRIC_RULES`/`evaluate_metric_status`)이 정본이며,
여기서 임계값을 다시 짜지 않는다. 두 입력 경로를 지원한다:

1. `derive_from_evaluated(items)` — **1순위**: health_metric 평가 결과물
   (`HealthMetricEvaluationItem`/`HealthMetricAnalysis.results_payload`: canonical_test_code + status).
   이미 검증된 출력을 그대로 소비(재계산 없음) — "여기서 나온 결과물을 PKG로".
2. `derive_conditions_and_flags(metrics)` — 폴백: record.CheckupMetricResult 원시 수치(metric_code+value).
   동일 룰엔진으로 status를 재평가한다(평가 결과물이 없을 때).

규칙: `status == RISK → 조건`. 예외로 공복혈당(FPG)은 CAUTION 대역이 곧 당뇨 전단계이므로
CAUTION → prediabetes, RISK → type2_diabetes.
"""

from dataclasses import dataclass
from typing import Any

from app.domains.health_metric.metric_evaluator import (
    OCR_CODE_TO_CANONICAL,
    SEX_SPECIFIC_CANONICALS,
    evaluate_metric_status,
)

# canonical 지표코드 → (RISK일 때) 조건 id. FPG는 아래에서 별도 처리.
_RISK_TO_CONDITION: dict[str, str] = {
    "BP_SYS": "hypertension",
    "BP_DIA": "hypertension",
    "TC": "dyslipidemia",
    "LDL": "dyslipidemia",
    "TG": "dyslipidemia",
    "HDL": "dyslipidemia",
    "EGFR": "ckd",
    "CREATININE": "ckd",
    "HGB": "anemia",
    "BMI": "obesity",
    "WAIST": "obesity",
    "AST": "fatty_liver",
    "ALT": "fatty_liver",
    "GGT": "fatty_liver",
    "PHQ9": "depression_screen",
}

# 결정론적 출력 순서(테스트·표시 안정화).
_CONDITION_ORDER: tuple[str, ...] = (
    "hypertension",
    "prediabetes",
    "type2_diabetes",
    "dyslipidemia",
    "obesity",
    "fatty_liver",
    "ckd",
    "anemia",
    "depression_screen",
    "cardiovascular_disease",
    "gout",
    "insomnia",
    "gerd",
    "ankle_edema",
    "osteoarthritis",
)

# 심혈관 위험 플래그를 켜는 조건들(2개 이상 동반 시).
_CVD_COMPONENTS = frozenset({"hypertension", "dyslipidemia", "type2_diabetes"})


@dataclass(frozen=True)
class MetricReading:
    """record.CheckupMetricResult 원시 입력(코드·값). status는 여기서 재평가한다(폴백 경로)."""

    metric_code: str
    value: str | None


def _base_canonical(metric_code: str) -> str | None:
    """OCR 코드공간(fasting_glucose 등) → canonical(FPG). 성별전용은 기본코드로 축약."""
    normalized = metric_code.strip().lower().replace("-", "_")
    canonical = OCR_CODE_TO_CANONICAL.get(normalized)
    if canonical is None:
        return None
    if canonical in SEX_SPECIFIC_CANONICALS:
        canonical = SEX_SPECIFIC_CANONICALS[canonical][0]
    return canonical


def _conditions_from_pairs(pairs: list[tuple[str | None, str | None]]) -> set[str]:
    """(canonical_test_code, status) 쌍 → 조건 집합. status는 대소문자 무관."""
    found: set[str] = set()
    for canonical, status in pairs:
        if not canonical or not status:
            continue
        s = status.strip().upper()
        if canonical == "FPG":
            if s == "CAUTION":
                found.add("prediabetes")
            elif s == "RISK":
                found.add("type2_diabetes")
        elif s == "RISK" and canonical in _RISK_TO_CONDITION:
            found.add(_RISK_TO_CONDITION[canonical])
    return found


def _flags(found: set[str], risk_level: str | None) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    if (
        len(_CVD_COMPONENTS & found) >= 2
        or "cardiovascular_disease" in found
        or (risk_level or "").upper() == "HIGH_RISK"
    ):
        flags["cardiovascular_risk"] = True
    return flags


def _ordered(found: set[str]) -> list[str]:
    return [c for c in _CONDITION_ORDER if c in found]


def _item_field(item: Any, key: str) -> Any:
    return item.get(key) if isinstance(item, dict) else getattr(item, key, None)


def derive_from_evaluated(
    items: list[Any],
    *,
    risk_level: str | None = None,
) -> tuple[list[str], dict[str, bool]]:
    """health_metric 평가 결과물(canonical_test_code + status) → 조건/플래그. (1순위 경로)

    Args:
        items: HealthMetricEvaluationItem 또는 그 dict(HealthMetricAnalysis.results_payload).
        risk_level: 분석 summary 위험도(HIGH_RISK 시 심혈관 위험 보강).
    """
    pairs = [(_item_field(it, "canonical_test_code"), _item_field(it, "status")) for it in items]
    found = _conditions_from_pairs(pairs)
    return _ordered(found), _flags(found, risk_level)


def derive_conditions_and_flags(
    metrics: list[MetricReading],
    *,
    sex: str | None = None,
    risk_level: str | None = None,
) -> tuple[list[str], dict[str, bool]]:
    """record.CheckupMetricResult 원시 수치 → 조건/플래그 (폴백 경로, 동일 룰엔진으로 재평가)."""
    pairs = [
        (_base_canonical(m.metric_code), evaluate_metric_status(m.metric_code, m.value, sex=sex))
        for m in metrics
    ]
    found = _conditions_from_pairs(pairs)
    return _ordered(found), _flags(found, risk_level)
