"""검진 metric_code → 상태(NORMAL/CAUTION/RISK/UNKNOWN) 평가."""

from app.domains.health_metric.service import (
    METRIC_RULES,
    STATUS_LABELS,
    EvaluationContext,
)

OCR_CODE_TO_CANONICAL: dict[str, str] = {
    "bmi": "BMI",
    "waist": "WAIST",
    "fasting_glucose": "FPG",
    "hemoglobin": "HGB",
    "systolic_bp": "BP_SYS",
    "diastolic_bp": "BP_DIA",
    "total_cholesterol": "TC",
    "hdl": "HDL",
    "ldl": "LDL",
    "triglyceride": "TG",
    "creatinine": "CREATININE",
    "egfr": "EGFR",
    "ast": "AST",
    "alt": "ALT",
    "gamma_gtp": "GGT",
}

_STATUS_MAP = {
    "normal": "NORMAL",
    "caution": "CAUTION",
    "risk": "RISK",
    "unknown": "UNKNOWN",
}


def evaluate_metric_status(
    metric_code: str,
    value: str | None,
    *,
    sex: str | None = None,
) -> str | None:
    if value is None or value.strip() == "":
        return None
    canonical = OCR_CODE_TO_CANONICAL.get(metric_code)
    if canonical is None:
        return "UNKNOWN"
    rule = METRIC_RULES.get(canonical)
    if rule is None:
        return "UNKNOWN"
    try:
        numeric = float(value.replace(",", ""))
    except ValueError:
        return "UNKNOWN"
    ctx = EvaluationContext(sex=_normalize_sex(sex))
    result = rule.evaluator(numeric, ctx)
    return _STATUS_MAP.get(result.status, "UNKNOWN")


def status_label(status: str | None) -> str | None:
    if status is None:
        return None
    reverse = {v: STATUS_LABELS[k] for k, v in _STATUS_MAP.items()}
    return reverse.get(status)


def _normalize_sex(sex: str | None) -> str | None:
    if sex is None:
        return None
    normalized = sex.strip().lower()
    if normalized in {"m", "male", "man", "남", "남성"}:
        return "male"
    if normalized in {"f", "female", "woman", "여", "여성"}:
        return "female"
    return None
