"""검진 지표 추세 계산(순수 함수) — 방향·잡음 임계·극성(adverse)·그룹핑.

- compute_trends: canonical별 시계열(오름차순 값) → MetricTrend. DB 불필요.
- group_trend_values: 원시 (metric_code, value) 시퀀스 → canonical별 float 리스트.

극성(adverse) 규칙: 혈압·혈당·BMI·LDL 등은 올라갈 때, HDL·eGFR·혈색소는 내려갈 때 불리.
"""

from app.domains.pkg.trends import compute_trends, group_trend_values


def _by_code(trends):
    return {t.code: t for t in trends}


# --- compute_trends ---


def test_rising_adverse_metric_is_up_and_adverse() -> None:
    t = _by_code(compute_trends({"BP_SYS": [120.0, 135.0]}))["BP_SYS"]
    assert t.direction == "up"
    assert t.adverse is True
    assert t.latest == 135.0 and t.previous == 120.0
    assert t.points == 2
    assert t.label  # 한국어 표시명 존재


def test_falling_hdl_is_adverse() -> None:
    t = _by_code(compute_trends({"HDL": [60.0, 45.0]}))["HDL"]
    assert t.direction == "down"
    assert t.adverse is True


def test_falling_egfr_is_adverse() -> None:
    t = _by_code(compute_trends({"EGFR": [90.0, 70.0]}))["EGFR"]
    assert t.direction == "down"
    assert t.adverse is True


def test_rising_hdl_is_not_adverse() -> None:
    t = _by_code(compute_trends({"HDL": [40.0, 55.0]}))["HDL"]
    assert t.direction == "up"
    assert t.adverse is False


def test_small_change_within_threshold_is_flat() -> None:
    # 120 -> 122 (1.7% < 임계) → flat, 악화 아님
    t = _by_code(compute_trends({"BP_SYS": [120.0, 122.0]}))["BP_SYS"]
    assert t.direction == "flat"
    assert t.adverse is False


def test_single_point_is_skipped() -> None:
    assert compute_trends({"BP_SYS": [120.0]}) == []


def test_uses_last_two_points() -> None:
    t = _by_code(compute_trends({"FPG": [100.0, 200.0, 110.0]}))["FPG"]
    assert t.previous == 200.0 and t.latest == 110.0
    assert t.direction == "down"
    assert t.points == 3


def test_adverse_trends_sorted_first() -> None:
    trends = compute_trends(
        {
            "HDL": [40.0, 55.0],  # 유리(비악화)
            "BP_SYS": [120.0, 140.0],  # 악화
        }
    )
    assert trends[0].code == "BP_SYS"
    assert trends[0].adverse is True


# --- group_trend_values ---


def test_group_maps_raw_codes_to_canonical() -> None:
    grouped = group_trend_values(
        [
            ("systolic_bp", "120"),
            ("systolic_bp", "130"),
            ("fasting_glucose", "95"),
        ]
    )
    assert grouped["BP_SYS"] == [120.0, 130.0]
    assert grouped["FPG"] == [95.0]


def test_group_reduces_sex_specific_to_base() -> None:
    grouped = group_trend_values([("hemoglobin_female", "12.5")])
    assert grouped.get("HGB") == [12.5]


def test_group_parses_comma_separated_values() -> None:
    # 천 단위 콤마가 있어도 파싱(중증 고중성지방혈증 등 4자리 값 대비).
    grouped = group_trend_values([("triglyceride", "1,200")])
    assert grouped["TG"] == [1200.0]


def test_group_skips_unparseable_and_untracked() -> None:
    grouped = group_trend_values(
        [
            ("systolic_bp", "abc"),  # 파싱 불가
            ("systolic_bp", ""),  # 빈 값
            ("unknown_code", "10"),  # 미추적 코드
            ("systolic_bp", "125"),  # 정상
        ]
    )
    assert grouped["BP_SYS"] == [125.0]
    assert "unknown_code" not in grouped
