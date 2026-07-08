"""검진 지표 추세(궤적) 계산 — 순수 함수.

같은 조건이라도 "이 사람의 지표가 오르는 중이냐 내리는 중이냐"는 사람마다 다르다.
그 궤적을 미션 개인화 신호(MetricTrend)로 만든다. DB에 의존하지 않는다:
build_pkg가 시계열을 조회해 (metric_code, value) 시퀀스로 넘기면 여기서 계산만 한다.

방향은 최근 두 관측의 상대변화로 판정(잡음 임계 적용). adverse(불리 여부)는 지표 극성:
혈압·혈당·BMI·LDL·간효소 등은 상승이, HDL·eGFR·혈색소는 하락이 건강에 불리하다.
"""

from collections.abc import Iterable
from typing import Literal

from app.domains.mission.schemas import MetricTrend
from app.domains.pkg.adapter import _base_canonical

# 추적 대상 canonical 지표 → 한국어 표시명(LLM 컨텍스트·설명용).
TREND_METRIC_LABELS: dict[str, str] = {
    "BP_SYS": "수축기 혈압",
    "BP_DIA": "이완기 혈압",
    "FPG": "공복혈당",
    "BMI": "체질량지수",
    "WAIST": "허리둘레",
    "TC": "총콜레스테롤",
    "LDL": "LDL 콜레스테롤",
    "HDL": "HDL 콜레스테롤",
    "TG": "중성지방",
    "EGFR": "eGFR(신장기능)",
    "CREATININE": "크레아티닌",
    "HGB": "혈색소",
    "AST": "AST(간효소)",
    "ALT": "ALT(간효소)",
    "GGT": "감마-GTP",
}

# 값이 '내려갈 때' 건강에 불리한 지표. 그 외 추적 지표는 '올라갈 때' 불리.
_DOWN_IS_ADVERSE = frozenset({"HDL", "EGFR", "HGB"})

# 최근 두 관측의 상대변화가 이 값을 넘어야 방향으로 인정(잡음 무시).
_TREND_EPS = 0.03


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def group_trend_values(rows: Iterable[tuple[str, str | None]]) -> dict[str, list[float]]:
    """원시 (metric_code, value) 시퀀스(날짜 오름차순) → canonical별 float 리스트.

    성별 전용 코드(HGB_F 등)는 기본 코드(HGB)로 축약한다. 파싱 불가·미추적 지표는 건너뛴다.
    """
    out: dict[str, list[float]] = {}
    for code, value in rows:
        canonical = _base_canonical(code)
        if canonical is None or canonical not in TREND_METRIC_LABELS:
            continue
        num = _parse_float(value)
        if num is None:
            continue
        out.setdefault(canonical, []).append(num)
    return out


def _direction(previous: float, latest: float) -> Literal["up", "down", "flat"]:
    if previous == 0:
        return "flat"
    pct = (latest - previous) / abs(previous)
    if pct > _TREND_EPS:
        return "up"
    if pct < -_TREND_EPS:
        return "down"
    return "flat"


def _is_adverse(code: str, direction: str) -> bool:
    if direction == "flat":
        return False
    if code in _DOWN_IS_ADVERSE:
        return direction == "down"
    return direction == "up"


def compute_trends(values_by_code: dict[str, list[float]]) -> list[MetricTrend]:
    """canonical별 시계열(오름차순 값) → MetricTrend 목록.

    관측이 2회 미만인 지표는 방향을 판단할 수 없어 제외한다. 악화 추세를 먼저,
    그다음 코드 순으로 정렬해 결정론적으로 반환한다(미션이 악화 지표를 우선 겨냥하도록).
    """
    trends: list[MetricTrend] = []
    for code, values in values_by_code.items():
        if len(values) < 2:
            continue
        previous, latest = values[-2], values[-1]
        direction = _direction(previous, latest)
        trends.append(
            MetricTrend(
                code=code,
                label=TREND_METRIC_LABELS.get(code, code),
                direction=direction,
                latest=latest,
                previous=previous,
                delta=round(latest - previous, 3),
                points=len(values),
                adverse=_is_adverse(code, direction),
            )
        )
    trends.sort(key=lambda t: (not t.adverse, t.code))
    return trends
