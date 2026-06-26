from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.domains.health_metric.explanation_service import HealthMetricExplanationService
from app.domains.health_metric.models import HealthMetricAnalysis
from app.domains.health_metric.repository import HealthMetricAnalysisRepository
from app.domains.health_metric.schemas import (
    HealthMetricDetailView,
    HealthMetricEvaluationItem,
    HealthMetricEvaluationRequest,
    HealthMetricExplanation,
    HealthMetricMeaning,
    HealthMetricOverallSummary,
    HealthMetricRangeBar,
    HealthMetricRangeSegment,
    HealthMetricRecommendations,
    HealthMetricSummaryCard,
    HealthMetricSummaryView,
    HealthMetricTrend,
)


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


def _canonical_label(label: str) -> str | None:
    compact = label.strip()
    if compact in ALIASES:
        return ALIASES[compact]
    upper = compact.upper().replace("-", "_").replace(" ", "_")
    return ALIASES.get(upper)


class HealthMetricService:
    def get_reference(self, metric_code: str):
        """건강 항목 기준값·설명을 조회합니다."""
        raise NotImplementedError

    def build_metric_detail(self, record_id: int, metric_code: str):
        """CheckupMetricResult + HealthMetricReference + AnalysisSummary를 조합합니다."""
        raise NotImplementedError

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
    "LDL": ["기름진 음식 빈도 줄이기", "주 3회 이상 유산소 운동하기", "검진 결과를 전문가와 상담하기"],
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
) -> list[HealthMetricDetailView]:
    explanation_by_key = {
        (item.canonical_test_code, item.input_label): item
        for item in explanation.item_explanations
    }
    details: list[HealthMetricDetailView] = []
    for item in results:
        card = _summary_card(item)
        item_explanation = explanation_by_key.get(
            (item.canonical_test_code, item.input_label)
        )
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
                trend=HealthMetricTrend(title="최근 추이", points=[]),
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
    return HealthMetricRangeBar(
        min=min_value,
        max=max_value,
        marker=item.value,
        marker_percent=marker_percent,
        segments=[
            HealthMetricRangeSegment(
                label=label,
                from_value=from_value,
                to_value=to_value,
                color=color,
            )
            for label, from_value, to_value, color in segment_specs
        ],
    )


class HealthMetricAnalysisService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = HealthMetricAnalysisRepository(db)

    async def create(
        self,
        request: HealthMetricEvaluationRequest,
        user_id: int,
        measured_at: datetime | None,
    ) -> tuple[int, HealthMetricSummaryView]:
        results = HealthMetricService().evaluate_metrics(request)
        explanation = await HealthMetricExplanationService().build_explanation(
            request=request,
            results=results,
        )

        analysis = HealthMetricAnalysis(
            user_id=user_id,
            sex=request.sex,
            measured_at=measured_at,
            request_payload=request.model_dump(mode="json"),
            results_payload=[item.model_dump(mode="json") for item in results],
            explanation_payload=explanation.model_dump(mode="json"),
            summary_payload={},
            details_payload=[],
        )
        self._db.add(analysis)
        self._db.flush()

        summary = build_summary_view(results=results, explanation=explanation, analysis_id=analysis.id)
        details = build_detail_views(results=results, explanation=explanation, analysis_id=analysis.id)
        analysis.summary_payload = summary.model_dump(mode="json")
        analysis.details_payload = [detail.model_dump(mode="json") for detail in details]
        self._db.commit()
        self._db.refresh(analysis)

        return analysis.id, summary


def _fallback_meaning(item: HealthMetricEvaluationItem) -> str:
    return f"{item.name or item.input_label} 항목은 {item.status_label}으로 분류되었습니다."


def _recommendations(item: HealthMetricEvaluationItem) -> list[str]:
    if item.status == "normal":
        return ["현재 좋은 흐름 유지하기", "다음 검진 때도 같은 항목 확인하기", "무리한 변화보다 꾸준함 유지하기"]
    if item.canonical_test_code and item.canonical_test_code in RECOMMENDATIONS:
        return RECOMMENDATIONS[item.canonical_test_code]
    if item.status == "unknown":
        return ["항목명과 단위를 다시 확인하기", "지원되는 검진 항목인지 확인하기", "필요하면 결과지를 다시 등록하기"]
    return ["생활습관 점검하기", "같은 항목을 추적 확인하기", "필요하면 전문가와 상담하기"]
