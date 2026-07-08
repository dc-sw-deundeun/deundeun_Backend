import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, UnprocessableEntityException
from app.domains.health_metric.explanation_service import HealthMetricExplanationService
from app.domains.health_metric.models import (
    HealthMetricAnalysis,
    HealthMetricAnalysisHighlight,
    HealthMetricAnalysisItem,
    HealthMetricAnalysisItemRange,
    HealthMetricAnalysisItemRecommendation,
    HealthMetricAnalysisRangeSegment,
)
from app.domains.health_metric.repository import (
    HealthMetricAnalysisRepository,
    HealthMetricRepository,
)
from app.domains.health_metric.schemas import (
    HealthMetricActiveRangeSegment,
    HealthMetricAnalysisCreateRequest,
    HealthMetricAnalysisMetricInput,
    HealthMetricAnalysisResponse,
    HealthMetricDetailView,
    HealthMetricEvaluationItem,
    HealthMetricEvaluationRequest,
    HealthMetricExplanation,
    HealthMetricInput,
    HealthMetricItemExplanation,
    HealthMetricMeaning,
    HealthMetricOverallSummary,
    HealthMetricRangeBar,
    HealthMetricRangeSegment,
    HealthMetricRecommendations,
    HealthMetricSummaryCard,
    HealthMetricSummaryView,
    HealthMetricTrend,
    HealthMetricTrendPoint,
)
from app.domains.ocr.status import VerificationStatus
from app.domains.record.models import CheckupMetricResult, CheckupRecord
from app.domains.record.repository import RecordRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EvaluationContext:
    sex: str | None
    item9_positive: bool | None = None


@dataclass(frozen=True)
class Evaluation:
    status: str
    matched_rule: str
    note: str | None = None


@dataclass(frozen=True)
class MetricRule:
    canonical_code: str
    name: str
    evaluator: Callable[[float, EvaluationContext], Evaluation]
    unit: str | None = None


@dataclass(frozen=True)
class EvaluationSource:
    metric_code: str
    metric_name: str
    value: str | None
    unit: str | None
    raw_text: str | None
    metric_input: HealthMetricInput


STATUS_LABELS = {
    "normal": "정상",
    "caution": "주의",
    "risk": "위험",
    "unknown": "판정불가",
}


def _range(value: float, low: float, high: float) -> bool:
    return low <= value <= high


def _sex(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"m", "male", "man", "남", "남성"}:
        return "male"
    if normalized in {"f", "female", "woman", "여", "여성"}:
        return "female"
    return None


def _normal(rule: str) -> Evaluation:
    return Evaluation(status="normal", matched_rule=rule)


def _caution(rule: str, note: str | None = None) -> Evaluation:
    return Evaluation(status="caution", matched_rule=rule, note=note)


def _risk(rule: str, note: str | None = None) -> Evaluation:
    return Evaluation(status="risk", matched_rule=rule, note=note)


def _unknown(rule: str, note: str | None = None) -> Evaluation:
    return Evaluation(status="unknown", matched_rule=rule, note=note)


def _bmi(value: float, _: EvaluationContext) -> Evaluation:
    if _range(value, 18.5, 24.9):
        return _normal("18.5 <= BMI <= 24.9")
    if value < 18.5 or value < 30:
        return _caution("BMI < 18.5 or 24.9 < BMI < 30")
    return _risk("BMI >= 30")


def _waist(value: float, ctx: EvaluationContext) -> Evaluation:
    if ctx.sex == "male":
        return _normal("male WAIST < 90") if value < 90 else _risk("male WAIST >= 90")
    if ctx.sex == "female":
        return _normal("female WAIST < 85") if value < 85 else _risk("female WAIST >= 85")
    return _unknown("WAIST requires sex", "허리둘레 판정에는 성별이 필요합니다.")


def _hearing(value: float, _: EvaluationContext) -> Evaluation:
    return _normal("HEARING < 40") if value < 40 else _risk("HEARING >= 40")


def _bp_sys(value: float, _: EvaluationContext) -> Evaluation:
    if value < 120:
        return _normal("BP_SYS < 120")
    if value < 140:
        return _caution("120 <= BP_SYS <= 139")
    return _risk("BP_SYS >= 140")


def _bp_dia(value: float, _: EvaluationContext) -> Evaluation:
    if value < 80:
        return _normal("BP_DIA < 80")
    if value < 90:
        return _caution("80 <= BP_DIA <= 89")
    return _risk("BP_DIA >= 90")


def _hgb(value: float, ctx: EvaluationContext) -> Evaluation:
    if ctx.sex == "male":
        if value < 13:
            return _risk("male HGB < 13", "빈혈 의심")
        if _range(value, 13, 16.5):
            return _normal("13 <= male HGB <= 16.5")
        return _caution("male HGB > 16.5", "제공 기준표의 정상 범위를 벗어났습니다.")
    if ctx.sex == "female":
        if value < 12:
            return _risk("female HGB < 12", "빈혈 의심")
        if _range(value, 12, 15.5):
            return _normal("12 <= female HGB <= 15.5")
        return _caution("female HGB > 15.5", "제공 기준표의 정상 범위를 벗어났습니다.")
    return _unknown("HGB requires sex", "혈색소 판정에는 성별이 필요합니다.")


def _fpg(value: float, _: EvaluationContext) -> Evaluation:
    if value < 100:
        return _normal("FPG < 100")
    if value < 126:
        return _caution("100 <= FPG <= 125")
    return _risk("FPG >= 126")


def _tc(value: float, _: EvaluationContext) -> Evaluation:
    if value < 200:
        return _normal("TC < 200")
    if value < 240:
        return _caution("200 <= TC <= 239")
    return _risk("TC >= 240")


def _hdl(value: float, _: EvaluationContext) -> Evaluation:
    if value >= 60:
        return _normal("HDL >= 60")
    if value >= 40:
        return _caution("40 <= HDL <= 59")
    return _risk("HDL < 40")


def _tg(value: float, _: EvaluationContext) -> Evaluation:
    if value < 150:
        return _normal("TG < 150")
    if value < 200:
        return _caution("150 <= TG <= 199")
    if value >= 500:
        return _risk("TG >= 500", "매우 높음")
    return _risk("TG >= 200")


def _ldl(value: float, _: EvaluationContext) -> Evaluation:
    if value < 130:
        return _normal("LDL < 130")
    if value < 160:
        return _caution("130 <= LDL <= 159")
    if value >= 190:
        return _risk("LDL >= 190", "매우 높음")
    return _risk("LDL >= 160")


def _creatinine(value: float, _: EvaluationContext) -> Evaluation:
    return _normal("CREATININE <= 1.5") if value <= 1.5 else _risk("CREATININE > 1.5")


def _egfr(value: float, _: EvaluationContext) -> Evaluation:
    if value >= 60:
        return _normal("EGFR >= 60")
    if value >= 45:
        return _caution("45 <= EGFR <= 59")
    return _risk("EGFR < 45", "위험도 상승")


def _upper_limit(code: str, limit: float) -> Callable[[float, EvaluationContext], Evaluation]:
    def evaluate(value: float, _: EvaluationContext) -> Evaluation:
        return _normal(f"{code} <= {limit:g}") if value <= limit else _risk(f"{code} > {limit:g}")

    return evaluate


def _ggt(value: float, ctx: EvaluationContext) -> Evaluation:
    if ctx.sex == "male":
        return _normal("male GGT <= 63") if value <= 63 else _risk("male GGT > 63")
    if ctx.sex == "female":
        return _normal("female GGT <= 35") if value <= 35 else _risk("female GGT > 35")
    return _unknown("GGT requires sex", "감마지티피 판정에는 성별이 필요합니다.")


def _phq9(value: float, ctx: EvaluationContext) -> Evaluation:
    if ctx.item9_positive:
        return _risk("PHQ9 item9 positive", "9번 문항 양성 고위험")
    if value <= 4:
        return _normal("0 <= PHQ9 <= 4")
    if value <= 9:
        return _caution("5 <= PHQ9 <= 9")
    if value >= 20:
        return _risk("PHQ9 >= 20", "고위험")
    return _risk("PHQ9 >= 10")


def _cape15(value: float, _: EvaluationContext) -> Evaluation:
    return _normal("0 <= CAPE15 <= 5") if value <= 5 else _risk("CAPE15 >= 6")


def _bmd_t(value: float, _: EvaluationContext) -> Evaluation:
    if value >= -1:
        return _normal("BMD_T >= -1")
    if value > -2.5:
        return _caution("-2.5 < BMD_T < -1")
    return _risk("BMD_T <= -2.5")


def _pft_ratio(value: float, _: EvaluationContext) -> Evaluation:
    return _normal("PFT_RATIO >= 70") if value >= 70 else _risk("PFT_RATIO < 70")


def _cognitive(value: float, _: EvaluationContext) -> Evaluation:
    return _normal("0 <= COGNITIVE <= 5") if value <= 5 else _risk("COGNITIVE >= 6")


def _nicotine(value: float, _: EvaluationContext) -> Evaluation:
    if value <= 3:
        return _normal("0 <= NICOTINE <= 3")
    if value <= 6:
        return _caution("4 <= NICOTINE <= 6")
    return _risk("7 <= NICOTINE <= 10")


METRIC_RULES: dict[str, MetricRule] = {
    "BMI": MetricRule("BMI", "BMI", _bmi, "kg/m2"),
    "WAIST": MetricRule("WAIST", "허리둘레", _waist, "cm"),
    "HEARING": MetricRule("HEARING", "청력", _hearing, "dB"),
    "BP_SYS": MetricRule("BP_SYS", "수축기혈압", _bp_sys, "mmHg"),
    "BP_DIA": MetricRule("BP_DIA", "이완기혈압", _bp_dia, "mmHg"),
    "HGB": MetricRule("HGB", "혈색소", _hgb, "g/dL"),
    "FPG": MetricRule("FPG", "공복혈당", _fpg, "mg/dL"),
    "TC": MetricRule("TC", "총콜레스테롤", _tc, "mg/dL"),
    "HDL": MetricRule("HDL", "HDL", _hdl, "mg/dL"),
    "TG": MetricRule("TG", "중성지방", _tg, "mg/dL"),
    "LDL": MetricRule("LDL", "LDL", _ldl, "mg/dL"),
    "CREATININE": MetricRule("CREATININE", "혈청 크레아티닌", _creatinine, "mg/dL"),
    "EGFR": MetricRule("EGFR", "e-GFR", _egfr, "mL/min/1.73m2"),
    "AST": MetricRule("AST", "AST", _upper_limit("AST", 40), "U/L"),
    "ALT": MetricRule("ALT", "ALT", _upper_limit("ALT", 35), "U/L"),
    "GGT": MetricRule("GGT", "감마지티피", _ggt, "U/L"),
    "PHQ9": MetricRule("PHQ9", "우울증", _phq9, "점"),
    "CAPE15": MetricRule("CAPE15", "조기정신증", _cape15, "점"),
    "BMD_T": MetricRule("BMD_T", "골밀도 T-score", _bmd_t),
    "PFT_RATIO": MetricRule("PFT_RATIO", "FEV1/FVC", _pft_ratio, "%"),
    "COGNITIVE": MetricRule("COGNITIVE", "인지기능", _cognitive, "점"),
    "NICOTINE": MetricRule("NICOTINE", "니코틴 의존도", _nicotine, "점"),
}


ALIASES = {
    "BMI": "BMI",
    "체질량지수": "BMI",
    "WAIST": "WAIST",
    "허리둘레": "WAIST",
    "HEARING": "HEARING",
    "청력": "HEARING",
    "BP_SYS": "BP_SYS",
    "수축기혈압": "BP_SYS",
    "BP_DIA": "BP_DIA",
    "이완기혈압": "BP_DIA",
    "HGB": "HGB",
    "HGB_M": "HGB_M",
    "HGB_F": "HGB_F",
    "혈색소": "HGB",
    "혈색소 남성": "HGB_M",
    "혈색소 여성": "HGB_F",
    "FPG": "FPG",
    "공복혈당": "FPG",
    "TC": "TC",
    "총콜레스테롤": "TC",
    "HDL": "HDL",
    "HDL 콜레스테롤": "HDL",
    "TG": "TG",
    "중성지방": "TG",
    "LDL": "LDL",
    "LDL 콜레스테롤": "LDL",
    "CREATININE": "CREATININE",
    "혈청 크레아티닌": "CREATININE",
    "크레아티닌": "CREATININE",
    "EGFR": "EGFR",
    "E_GFR": "EGFR",
    "e-GFR": "EGFR",
    "추정 사구체여과율": "EGFR",
    "AST": "AST",
    "ALT": "ALT",
    "GGT": "GGT",
    "GGT_M": "GGT_M",
    "GGT_F": "GGT_F",
    "감마지티피": "GGT",
    "γ-GTP": "GGT",
    "γ-GTP 남성": "GGT_M",
    "γ-GTP 여성": "GGT_F",
    "PHQ9": "PHQ9",
    "우울증": "PHQ9",
    "CAPE15": "CAPE15",
    "조기정신증": "CAPE15",
    "BMD_T": "BMD_T",
    "골밀도 T-score": "BMD_T",
    "PFT_RATIO": "PFT_RATIO",
    "FEV1/FVC": "PFT_RATIO",
    "COGNITIVE": "COGNITIVE",
    "인지기능": "COGNITIVE",
    "NICOTINE": "NICOTINE",
    "니코틴 의존도": "NICOTINE",
}

RECORD_METRIC_CODE_ALIASES = {
    "bmi": "BMI",
    "waist": "WAIST",
    "systolic_bp": "BP_SYS",
    "diastolic_bp": "BP_DIA",
    "hemoglobin": "HGB",
    "fasting_glucose": "FPG",
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


def _canonical_label(label: str) -> str | None:
    compact = label.strip()
    if compact in ALIASES:
        return ALIASES[compact]
    upper = compact.upper().replace("-", "_").replace(" ", "_")
    return ALIASES.get(upper)


class HealthMetricService:
    def __init__(self, db: Session | None = None) -> None:
        self._db = db

    def get_reference(self, metric_code: str):
        """건강 항목 기준값·설명을 조회합니다."""
        if self._db is None:
            raise RuntimeError("HealthMetricService requires a DB session for reference lookup")
        return HealthMetricRepository(self._db).find_by_metric_code(metric_code)

    def build_metric_detail(self, record_id: int, metric_code: str) -> dict:
        """CheckupMetricResult + HealthMetricReference 조합 (분석 요약은 Phase 4)."""
        if self._db is None:
            raise RuntimeError("HealthMetricService requires a DB session for metric detail")
        reference = self.get_reference(metric_code)
        return {
            "record_id": record_id,
            "metric_code": metric_code,
            "reference": reference,
            "analysis_summary": None,
        }

    def evaluate_metrics(
        self, request: HealthMetricEvaluationRequest
    ) -> list[HealthMetricEvaluationItem]:
        sex = _sex(request.sex)
        results: list[HealthMetricEvaluationItem] = []

        for metric in request.metrics:
            alias = _canonical_label(metric.label)
            rule_sex = sex
            canonical_code = alias

            if alias == "HGB_M":
                canonical_code = "HGB"
                rule_sex = "male"
            elif alias == "HGB_F":
                canonical_code = "HGB"
                rule_sex = "female"
            elif alias == "GGT_M":
                canonical_code = "GGT"
                rule_sex = "male"
            elif alias == "GGT_F":
                canonical_code = "GGT"
                rule_sex = "female"

            rule = METRIC_RULES.get(canonical_code or "")
            if rule is None:
                results.append(
                    HealthMetricEvaluationItem(
                        input_label=metric.label,
                        canonical_test_code=None,
                        name=None,
                        value=metric.value,
                        unit=metric.unit,
                        status="unknown",
                        status_label=STATUS_LABELS["unknown"],
                        matched_rule=None,
                        note="지원하지 않는 검진 항목입니다.",
                    )
                )
                continue

            evaluation = rule.evaluator(
                metric.value,
                EvaluationContext(sex=rule_sex, item9_positive=metric.item9_positive),
            )
            results.append(
                HealthMetricEvaluationItem(
                    input_label=metric.label,
                    canonical_test_code=rule.canonical_code,
                    name=rule.name,
                    value=metric.value,
                    unit=metric.unit or rule.unit,
                    status=evaluation.status,
                    status_label=STATUS_LABELS[evaluation.status],
                    matched_rule=evaluation.matched_rule,
                    note=evaluation.note,
                )
            )

        return results


RANGE_BAR_CONFIGS: dict[str, tuple[float, float, list[tuple[str, float, float, str]]]] = {
    "BMI": (
        10,
        35,
        [
            ("주의 <18.5", 10, 18.4, "yellow"),
            ("정상 18.5~24.9", 18.5, 24.9, "green"),
            ("주의 24.9~29.9", 24.9, 29.9, "yellow"),
            ("위험 30~", 30, 35, "red"),
        ],
    ),
    "WAIST": (
        60,
        110,
        [
            ("정상", 60, 89, "green"),
            ("위험", 90, 110, "red"),
        ],
    ),
    "BP_SYS": (
        80,
        180,
        [
            ("정상 <120", 80, 119, "green"),
            ("주의 120~139", 120, 139, "yellow"),
            ("위험 140~", 140, 180, "red"),
        ],
    ),
    "BP_DIA": (
        50,
        120,
        [
            ("정상 <80", 50, 79, "green"),
            ("주의 80~89", 80, 89, "yellow"),
            ("위험 90~", 90, 120, "red"),
        ],
    ),
    "FPG": (
        70,
        160,
        [
            ("안심 ~99", 70, 99, "green"),
            ("경계 100~125", 100, 125, "yellow"),
            ("위험 126~", 126, 160, "red"),
        ],
    ),
    "TC": (
        100,
        280,
        [
            ("정상 <200", 100, 199, "green"),
            ("주의 200~239", 200, 239, "yellow"),
            ("위험 240~", 240, 280, "red"),
        ],
    ),
    "HDL": (
        20,
        90,
        [
            ("위험 <40", 20, 39, "red"),
            ("주의 40~59", 40, 59, "yellow"),
            ("정상 60~", 60, 90, "green"),
        ],
    ),
    "TG": (
        50,
        550,
        [
            ("정상 <150", 50, 149, "green"),
            ("주의 150~199", 150, 199, "yellow"),
            ("위험 200~499", 200, 499, "red"),
            ("매우 높음 500~", 500, 550, "red"),
        ],
    ),
    "LDL": (
        50,
        220,
        [
            ("정상 <130", 50, 129, "green"),
            ("주의 130~159", 130, 159, "yellow"),
            ("위험 160~189", 160, 189, "red"),
            ("매우 높음 190~", 190, 220, "red"),
        ],
    ),
    "EGFR": (
        20,
        100,
        [
            ("위험 <45", 20, 44, "red"),
            ("주의 45~59", 45, 59, "yellow"),
            ("정상 60~", 60, 100, "green"),
        ],
    ),
    "AST": (
        0,
        100,
        [
            ("정상 ~40", 0, 40, "green"),
            ("위험 40~", 41, 100, "red"),
        ],
    ),
    "ALT": (
        0,
        100,
        [
            ("정상 ~35", 0, 35, "green"),
            ("위험 35~", 36, 100, "red"),
        ],
    ),
}


RECOMMENDATIONS: dict[str, list[str]] = {
    "FPG": ["식후 30분 가볍게 걷기", "단 음료 대신 물 마시기", "식사 때 채소를 먼저 먹기"],
    "LDL": [
        "기름진 음식 빈도 줄이기",
        "주 3회 이상 유산소 운동하기",
        "검진 결과를 전문가와 상담하기",
    ],
    "TG": ["술과 단 음료 줄이기", "야식과 과식 줄이기", "빠른 시일 내 전문가와 상담하기"],
    "WAIST": ["하루 걸음 수 늘리기", "늦은 밤 간식 줄이기", "허리둘레를 주기적으로 기록하기"],
    "BMI": ["현재 습관 유지하기", "주기적으로 체중 확인하기", "근력 운동을 함께 하기"],
}


def build_summary_view(
    results: list[HealthMetricEvaluationItem],
    explanation: HealthMetricExplanation,
    analysis_id: int | None = None,
) -> HealthMetricSummaryView:
    counts = {"normal": 0, "caution": 0, "risk": 0, "unknown": 0}
    for item in results:
        counts[item.status] = counts.get(item.status, 0) + 1

    if counts["risk"] > 0:
        title = "관리가 필요해요"
    elif counts["caution"] > 0:
        title = "주의가 필요해요"
    else:
        title = "잘 유지하고 있어요"

    summary = (
        explanation.summary
        or f"정상 {counts['normal']}개, 주의 {counts['caution']}개, 위험 {counts['risk']}개입니다."
    )

    return HealthMetricSummaryView(
        analysis_id=analysis_id,
        overall=HealthMetricOverallSummary(title=title, summary=summary, counts=counts),
        cards=[_summary_card(item) for item in results],
    )


def build_detail_views(
    results: list[HealthMetricEvaluationItem],
    explanation: HealthMetricExplanation,
    analysis_id: int | None = None,
    trend_points_by_code: dict[str, list[HealthMetricTrendPoint]] | None = None,
) -> list[HealthMetricDetailView]:
    explanation_by_key = {
        (item.canonical_test_code, item.input_label): item for item in explanation.item_explanations
    }
    details: list[HealthMetricDetailView] = []
    for item in results:
        card = _summary_card(item)
        item_explanation = explanation_by_key.get((item.canonical_test_code, item.input_label))
        body = (
            item_explanation.explanation
            if item_explanation is not None
            else _fallback_meaning(item)
        )
        details.append(
            HealthMetricDetailView(
                analysis_id=analysis_id,
                metric=card,
                range_bar=card.range_bar,
                trend=HealthMetricTrend(
                    title="최근 추이",
                    points=(
                        trend_points_by_code.get(item.canonical_test_code, [])
                        if item.canonical_test_code and trend_points_by_code
                        else []
                    ),
                ),
                meaning=HealthMetricMeaning(title="이게 무슨 의미일까요?", body=body),
                recommendations=HealthMetricRecommendations(
                    title="맞춤 추천 습관",
                    items=_recommendations(item),
                ),
            )
        )
    return details


def _summary_card(item: HealthMetricEvaluationItem) -> HealthMetricSummaryCard:
    label = item.name or item.input_label
    return HealthMetricSummaryCard(
        code=item.canonical_test_code,
        label=label,
        value=item.value,
        unit=item.unit,
        status=item.status,
        status_label=item.status_label,
        value_text=_value_text(item),
        badge_text=_badge_text(item),
        range_bar=_range_bar(item),
    )


def _value_text(item: HealthMetricEvaluationItem) -> str:
    return f"{item.value:g} {item.unit}" if item.unit else f"{item.value:g}"


def _badge_text(item: HealthMetricEvaluationItem) -> str:
    if item.note:
        return f"{item.status_label} · {item.note}"
    return item.status_label


def _range_bar(item: HealthMetricEvaluationItem) -> HealthMetricRangeBar | None:
    if item.canonical_test_code is None:
        return None
    config = RANGE_BAR_CONFIGS.get(item.canonical_test_code)
    if config is None:
        return None
    min_value, max_value, segment_specs = config
    marker = max(min(item.value, max_value), min_value)
    marker_percent = round(((marker - min_value) / (max_value - min_value)) * 100, 2)
    segments = [
        HealthMetricRangeSegment(
            label=label,
            from_value=from_value,
            to_value=to_value,
            color=color,
        )
        for label, from_value, to_value, color in segment_specs
    ]
    return HealthMetricRangeBar(
        min=min_value,
        max=max_value,
        marker=item.value,
        marker_percent=marker_percent,
        segments=segments,
        active_segment=_active_segment(marker, segments),
    )


def _active_segment(
    marker: float, segments: list[HealthMetricRangeSegment]
) -> HealthMetricActiveRangeSegment | None:
    if not segments:
        return None
    segment = next(
        (segment for segment in segments if segment.from_value <= marker <= segment.to_value),
        None,
    )
    if segment is None:
        segment = segments[0] if marker < segments[0].from_value else segments[-1]

    span = segment.to_value - segment.from_value
    if span <= 0:
        marker_percent = 100.0
    else:
        clamped_marker = max(min(marker, segment.to_value), segment.from_value)
        marker_percent = round(((clamped_marker - segment.from_value) / span) * 100, 2)

    return HealthMetricActiveRangeSegment(
        label=segment.label,
        from_value=segment.from_value,
        to_value=segment.to_value,
        color=segment.color,
        marker_percent=marker_percent,
    )


class HealthMetricAnalysisService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = HealthMetricAnalysisRepository(db)
        self._record_repo = RecordRepository(db)

    async def create(
        self,
        request: HealthMetricAnalysisCreateRequest,
        user_id: int,
        measured_at: datetime | None,
    ) -> HealthMetricAnalysisResponse:
        record = self._validated_record(user_id=user_id, record_id=request.record_id)
        effective_measured_at = measured_at or (record.measured_at if record is not None else None)
        sources = self._to_evaluation_sources(request)
        if not sources:
            raise UnprocessableEntityException(
                message="분석 가능한 건강검진 항목이 없습니다.",
                error_code="NO_ANALYZABLE_HEALTH_METRICS",
            )
        evaluation_request = HealthMetricEvaluationRequest(
            sex=request.sex,
            measured_at=request.measured_at,
            metrics=[source.metric_input for source in sources],
        )
        results = HealthMetricService().evaluate_metrics(evaluation_request)
        explanation = await HealthMetricExplanationService().build_explanation(
            request=evaluation_request,
            results=results,
        )
        trend_points_by_code = self._analysis_trend_points_by_code(
            user_id=user_id,
            results=results,
            measured_at=effective_measured_at,
        )
        summary = build_summary_view(results=results, explanation=explanation)

        analysis = HealthMetricAnalysis(
            user_id=user_id,
            record_id=record.id if record is not None else None,
            sex=request.sex,
            measured_at=effective_measured_at,
            overall_title=summary.overall.title,
            overall_summary=summary.overall.summary,
            normal_count=summary.overall.counts.get("normal", 0),
            caution_count=summary.overall.counts.get("caution", 0),
            risk_count=summary.overall.counts.get("risk", 0),
            unknown_count=summary.overall.counts.get("unknown", 0),
            explanation_status=explanation.status,
            disclaimer=explanation.disclaimer,
        )
        self._repo.save(analysis)

        summary = build_summary_view(
            results=results, explanation=explanation, analysis_id=analysis.id
        )
        details = build_detail_views(
            results=results,
            explanation=explanation,
            analysis_id=analysis.id,
            trend_points_by_code=trend_points_by_code,
        )
        analysis.overall_title = summary.overall.title
        self._save_normalized_children(
            analysis=analysis,
            sources=sources,
            results=results,
            explanation=explanation,
            details=details,
        )
        if record is not None:
            self._record_repo.set_analysis_status(record, "COMPLETED")
        self._db.commit()
        self._db.refresh(analysis)

        # 지연 임포트: mission.generation_service -> pkg -> health_metric.metric_evaluator
        # -> health_metric.service 순환을 피한다(pkg 관련 임포트는 이 모듈에서 항상 지연 로드).
        from app.domains.mission.generation_service import trigger_checkup_regeneration

        # PKG 재빌드 + 당일 미션 재생성(best-effort, PKG 성공 시에만 재생성 트리거).
        # 트리거가 예기치 않게 실패해도 이미 커밋된 분석 저장에는 영향 없다.
        try:
            trigger_checkup_regeneration(user_id, self._db)
        except Exception:
            logger.warning(
                "mission generation trigger failed after health metric save (user_id=%s)",
                user_id,
                exc_info=True,
            )

        response = self._to_response(analysis)
        self._notify_analysis_completed(user_id=user_id, analysis_id=analysis.id)
        return response

    def _notify_analysis_completed(self, *, user_id: int, analysis_id: int) -> None:
        from app.domains.notification.repository import NotificationRepository
        from app.domains.notification.service import NotificationService, run_notification_safely

        def notify() -> None:
            NotificationService(NotificationRepository(self._db)).notify_analysis_completed(
                user_id=user_id,
                analysis_id=analysis_id,
                commit=False,
            )

        run_notification_safely(
            self._db,
            notify,
            logger,
            "ANALYSIS_COMPLETED notification failed (user_id=%s, analysis_id=%s)",
            user_id,
            analysis_id,
        )

    def get(self, analysis_id: int, user_id: int) -> HealthMetricAnalysisResponse:
        analysis = self._repo.get_for_user(analysis_id, user_id)
        if analysis is None:
            raise NotFoundException(
                message="건강검진 분석을 찾을 수 없습니다.",
                error_code="HEALTH_METRIC_ANALYSIS_NOT_FOUND",
            )
        return self._to_response(analysis)

    def get_latest_for_record(self, record_id: int, user_id: int) -> HealthMetricAnalysisResponse:
        record = self._record_repo.get_record_for_user(user_id, record_id)
        if record is None:
            raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
        analysis = self._repo.get_latest_for_record(record_id, user_id)
        if analysis is None:
            raise NotFoundException(
                message="검진 기록에 연결된 건강검진 분석을 찾을 수 없습니다.",
                error_code="HEALTH_METRIC_ANALYSIS_NOT_FOUND",
            )
        return self._to_response(analysis)

    def _validated_record(self, *, user_id: int, record_id: int | None) -> CheckupRecord | None:
        if record_id is None:
            return None
        record = self._record_repo.get_record_for_user(user_id, record_id)
        if record is None:
            raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
        if (
            record.source_type != "MANUAL"
            and record.verification_status != VerificationStatus.VERIFIED.value
        ):
            raise ConflictException(
                message="검수가 완료되지 않은 기록은 분석할 수 없습니다.",
                error_code="NOT_VERIFIED",
            )
        return record

    def _to_evaluation_sources(
        self, request: HealthMetricAnalysisCreateRequest
    ) -> list[EvaluationSource]:
        return [
            source
            for source in (self._to_evaluation_source(metric) for metric in request.metrics)
            if source is not None
        ]

    def _to_evaluation_source(
        self, metric: HealthMetricAnalysisMetricInput
    ) -> EvaluationSource | None:
        value = _parse_metric_value(metric.value)
        if value is None:
            return None

        canonical = _canonical_metric(metric.metric_code, metric.metric_name)
        if canonical is None:
            return None

        rule_code = _rule_lookup_code(canonical)
        if rule_code not in METRIC_RULES:
            return None

        metric_input = HealthMetricInput(
            label=canonical,
            value=value,
            unit=metric.unit or None,
        )
        return EvaluationSource(
            metric_code=metric.metric_code,
            metric_name=metric.metric_name,
            value=metric.value,
            unit=metric.unit,
            raw_text=metric.raw_text,
            metric_input=metric_input,
        )

    def _save_normalized_children(
        self,
        *,
        analysis: HealthMetricAnalysis,
        sources: list[EvaluationSource],
        results: list[HealthMetricEvaluationItem],
        explanation: HealthMetricExplanation,
        details: list[HealthMetricDetailView],
    ) -> None:
        for index, highlight in enumerate(explanation.highlights):
            self._db.add(
                HealthMetricAnalysisHighlight(
                    analysis_id=analysis.id,
                    body=highlight,
                    sort_order=index,
                )
            )

        for index, (source, result, detail) in enumerate(
            zip(sources, results, details, strict=True)
        ):
            item = HealthMetricAnalysisItem(
                analysis_id=analysis.id,
                input_metric_code=source.metric_code,
                input_metric_name=source.metric_name,
                canonical_test_code=result.canonical_test_code or "",
                display_name=result.name or source.metric_name,
                value=result.value,
                unit=result.unit,
                raw_text=source.raw_text,
                status=result.status,
                status_label=result.status_label,
                matched_rule=result.matched_rule,
                note=result.note,
                explanation_title=detail.meaning.title,
                explanation_body=detail.meaning.body,
                value_text=detail.metric.value_text,
                badge_text=detail.metric.badge_text,
                sort_order=index,
            )
            self._db.add(item)
            self._db.flush()

            if detail.metric.range_bar is not None:
                self._save_range(item.id, detail.metric.range_bar)

            for recommendation_index, recommendation in enumerate(detail.recommendations.items):
                self._db.add(
                    HealthMetricAnalysisItemRecommendation(
                        item_id=item.id,
                        title=detail.recommendations.title,
                        body=recommendation,
                        sort_order=recommendation_index,
                    )
                )

    def _save_range(self, item_id: int, range_bar: HealthMetricRangeBar) -> None:
        active = range_bar.active_segment
        self._db.add(
            HealthMetricAnalysisItemRange(
                item_id=item_id,
                range_min=range_bar.min,
                range_max=range_bar.max,
                marker=range_bar.marker,
                marker_percent=range_bar.marker_percent,
                active_label=active.label if active else None,
                active_from_value=active.from_value if active else None,
                active_to_value=active.to_value if active else None,
                active_color=active.color if active else None,
                active_marker_percent=active.marker_percent if active else None,
            )
        )
        for index, segment in enumerate(range_bar.segments):
            self._db.add(
                HealthMetricAnalysisRangeSegment(
                    item_id=item_id,
                    label=segment.label,
                    from_value=segment.from_value,
                    to_value=segment.to_value,
                    color=segment.color,
                    sort_order=index,
                )
            )

    def _analysis_trend_points_by_code(
        self,
        *,
        user_id: int,
        results: list[HealthMetricEvaluationItem],
        measured_at: datetime | None,
    ) -> dict[str, list[HealthMetricTrendPoint]]:
        grouped: dict[str, list[HealthMetricTrendPoint]] = {
            item.canonical_test_code: [] for item in results if item.canonical_test_code is not None
        }
        if not grouped:
            return {}

        for analysis in self._repo.list_for_user(user_id):
            event_at = analysis.measured_at or analysis.created_at
            if event_at is None:
                continue
            label = event_at.date().isoformat()
            for item in analysis.items:
                code = item.canonical_test_code
                if code not in grouped:
                    continue
                grouped[code].append(HealthMetricTrendPoint(label=label, value=float(item.value)))

        current_label = (measured_at or datetime.now(UTC)).date().isoformat()
        for result in results:
            if result.canonical_test_code in grouped:
                grouped[result.canonical_test_code].append(
                    HealthMetricTrendPoint(label=current_label, value=result.value)
                )
        return grouped

    def _trend_points_by_code(
        self,
        *,
        user_id: int,
        record_id: int | None,
        results: list[HealthMetricEvaluationItem],
    ) -> dict[str, list[HealthMetricTrendPoint]]:
        if record_id is None:
            return {}

        target_codes = {
            item.canonical_test_code for item in results if item.canonical_test_code is not None
        }
        if not target_codes:
            return {}

        metrics = self._record_repo.list_metrics(record_id)
        metric_code_to_canonical: dict[str, str] = {}
        for metric in metrics:
            canonical = _canonical_record_metric(metric)
            if canonical in target_codes:
                metric_code_to_canonical[metric.metric_code] = canonical

        if not metric_code_to_canonical:
            return {}

        grouped: dict[str, list[HealthMetricTrendPoint]] = {code: [] for code in target_codes}
        series_rows = self._record_repo.list_trend_series(
            user_id,
            sorted(metric_code_to_canonical),
            verification_status=VerificationStatus.VERIFIED.value,
        )
        for record, metric in series_rows:
            canonical = metric_code_to_canonical.get(metric.metric_code)
            value = _parse_metric_value(metric.value)
            if canonical is None or value is None:
                continue
            event_at = record.measured_at or record.created_at
            grouped[canonical].append(
                HealthMetricTrendPoint(label=event_at.date().isoformat(), value=value)
            )
        return grouped

    def _to_response(self, analysis: HealthMetricAnalysis) -> HealthMetricAnalysisResponse:
        if not analysis.items and analysis.results_payload is not None:
            return self._legacy_payload_response(analysis)

        results = [
            HealthMetricEvaluationItem(
                input_label=item.input_metric_name,
                canonical_test_code=item.canonical_test_code,
                name=item.display_name,
                value=float(item.value),
                unit=item.unit,
                status=item.status,
                status_label=item.status_label,
                matched_rule=item.matched_rule,
                note=item.note,
            )
            for item in analysis.items
        ]
        if analysis.record_id is not None and analysis.user_id is not None:
            trend_points_by_code = self._trend_points_by_code(
                user_id=analysis.user_id,
                record_id=analysis.record_id,
                results=results,
            )
        else:
            trend_points_by_code = self._stored_analysis_trend_points_by_code(analysis)
        item_explanations = [
            HealthMetricItemExplanation(
                canonical_test_code=item.canonical_test_code,
                input_label=item.input_metric_name,
                title=item.display_name,
                explanation=item.explanation_body,
                status_label=item.status_label,
            )
            for item in analysis.items
        ]
        explanation = HealthMetricExplanation(
            status=analysis.explanation_status or "stored",
            summary=analysis.overall_summary or "",
            highlights=[highlight.body for highlight in analysis.highlights],
            item_explanations=item_explanations,
            disclaimer=analysis.disclaimer or "",
        )
        summary = HealthMetricSummaryView(
            analysis_id=analysis.id,
            overall=HealthMetricOverallSummary(
                title=analysis.overall_title or "",
                summary=analysis.overall_summary or "",
                counts={
                    "normal": analysis.normal_count,
                    "caution": analysis.caution_count,
                    "risk": analysis.risk_count,
                    "unknown": analysis.unknown_count,
                },
            ),
            cards=[_summary_card_from_analysis_item(item) for item in analysis.items],
        )
        details = [
            HealthMetricDetailView(
                analysis_id=analysis.id,
                metric=_summary_card_from_analysis_item(item),
                range_bar=_range_bar_from_analysis_item(item),
                trend=HealthMetricTrend(
                    title="최근 추이",
                    points=trend_points_by_code.get(item.canonical_test_code, []),
                ),
                meaning=HealthMetricMeaning(
                    title=item.explanation_title,
                    body=item.explanation_body,
                ),
                recommendations=HealthMetricRecommendations(
                    title=(
                        item.recommendations[0].title if item.recommendations else "맞춤 추천 습관"
                    ),
                    items=[recommendation.body for recommendation in item.recommendations],
                ),
            )
            for item in analysis.items
        ]
        return HealthMetricAnalysisResponse(
            analysis_id=analysis.id,
            record_id=analysis.record_id,
            results=results,
            explanation=explanation,
            ui={
                "summary": summary.model_dump(mode="json"),
                "details": [detail.model_dump(mode="json") for detail in details],
            },
        )

    def _legacy_payload_response(
        self, analysis: HealthMetricAnalysis
    ) -> HealthMetricAnalysisResponse:
        results = [
            HealthMetricEvaluationItem.model_validate(item)
            for item in (analysis.results_payload or [])
        ]
        explanation = HealthMetricExplanation.model_validate(analysis.explanation_payload or {})
        summary = HealthMetricSummaryView.model_validate(analysis.summary_payload or {})
        details = [
            HealthMetricDetailView.model_validate(item) for item in (analysis.details_payload or [])
        ]
        return HealthMetricAnalysisResponse(
            analysis_id=analysis.id,
            record_id=analysis.record_id,
            results=results,
            explanation=explanation,
            ui={
                "summary": summary.model_dump(mode="json"),
                "details": [detail.model_dump(mode="json") for detail in details],
            },
        )

    def _stored_analysis_trend_points_by_code(
        self, analysis: HealthMetricAnalysis
    ) -> dict[str, list[HealthMetricTrendPoint]]:
        codes = {item.canonical_test_code for item in analysis.items}
        grouped: dict[str, list[HealthMetricTrendPoint]] = {code: [] for code in codes}
        if not analysis.user_id:
            return grouped
        for previous_analysis in self._repo.list_for_user(analysis.user_id):
            if previous_analysis.id > analysis.id:
                continue
            event_at = previous_analysis.measured_at or previous_analysis.created_at
            if event_at is None:
                continue
            label = event_at.date().isoformat()
            for item in previous_analysis.items:
                if item.canonical_test_code in grouped:
                    grouped[item.canonical_test_code].append(
                        HealthMetricTrendPoint(label=label, value=float(item.value))
                    )
        return grouped


def _canonical_record_metric(metric: CheckupMetricResult) -> str | None:
    return (
        RECORD_METRIC_CODE_ALIASES.get(metric.metric_code.lower())
        or _canonical_label(metric.metric_code)
        or _canonical_label(metric.metric_name)
    )


def _summary_card_from_analysis_item(item: HealthMetricAnalysisItem) -> HealthMetricSummaryCard:
    return HealthMetricSummaryCard(
        code=item.canonical_test_code,
        label=item.display_name,
        value=float(item.value),
        unit=item.unit,
        status=item.status,
        status_label=item.status_label,
        value_text=item.value_text,
        badge_text=item.badge_text,
        range_bar=_range_bar_from_analysis_item(item),
    )


def _range_bar_from_analysis_item(item: HealthMetricAnalysisItem) -> HealthMetricRangeBar | None:
    stored_range = item.range
    if stored_range is None:
        return None

    active_segment = None
    if stored_range.active_label is not None:
        active_segment = HealthMetricActiveRangeSegment(
            label=stored_range.active_label,
            from_value=float(stored_range.active_from_value or 0),
            to_value=float(stored_range.active_to_value or 0),
            color=stored_range.active_color or "",
            marker_percent=float(stored_range.active_marker_percent or 0),
        )

    return HealthMetricRangeBar(
        min=float(stored_range.range_min),
        max=float(stored_range.range_max),
        marker=float(stored_range.marker),
        marker_percent=float(stored_range.marker_percent),
        segments=[
            HealthMetricRangeSegment(
                label=segment.label,
                from_value=float(segment.from_value),
                to_value=float(segment.to_value),
                color=segment.color,
            )
            for segment in item.range_segments
        ],
        active_segment=active_segment,
    )


def _canonical_metric(metric_code: str, metric_name: str) -> str | None:
    return (
        RECORD_METRIC_CODE_ALIASES.get(metric_code.lower())
        or _canonical_label(metric_code)
        or _canonical_label(metric_name)
    )


def _rule_lookup_code(canonical: str) -> str:
    if canonical in {"HGB_M", "HGB_F"}:
        return "HGB"
    if canonical in {"GGT_M", "GGT_F"}:
        return "GGT"
    return canonical


def _parse_metric_value(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None


def _fallback_meaning(item: HealthMetricEvaluationItem) -> str:
    return f"{item.name or item.input_label} 항목은 {item.status_label}으로 분류되었습니다."


def _recommendations(item: HealthMetricEvaluationItem) -> list[str]:
    if item.status == "normal":
        return [
            "현재 좋은 흐름 유지하기",
            "다음 검진 때도 같은 항목 확인하기",
            "무리한 변화보다 꾸준함 유지하기",
        ]
    if item.canonical_test_code and item.canonical_test_code in RECOMMENDATIONS:
        return RECOMMENDATIONS[item.canonical_test_code]
    if item.status == "unknown":
        return [
            "항목명과 단위를 다시 확인하기",
            "지원되는 검진 항목인지 확인하기",
            "필요하면 결과지를 다시 등록하기",
        ]
    return ["생활습관 점검하기", "같은 항목을 추적 확인하기", "필요하면 전문가와 상담하기"]
