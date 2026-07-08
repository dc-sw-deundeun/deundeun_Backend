"""외부 의학 KG 이웃 추출 코어 로직(순수) — 합성 행으로 매칭·방향성·중복·상한 검증.

extract_neighborhood는 kg.csv 없이 (relation, x_id, x_type, x_name, y_id, y_type, y_name)
행 시퀀스만 받아 조건별 {complications/phenotypes/exposures}를 만든다.
"""

from app.domains.pkg.neighborhood import extract_neighborhood

_MONDO = {"type2_diabetes": "5148", "ckd": "5300", "obesity": "11122"}


def _row(rel, xid, xn, yid, yn, xt="disease", yt="disease"):
    return (rel, xid, xt, xn, yid, yt, yn)


def test_disease_disease_collects_other_endpoint_both_directions() -> None:
    rows = [
        _row("disease_disease", "5148", "type 2 diabetes", "5300", "chronic kidney disease"),
        _row("disease_disease", "4995", "cardiovascular disease", "5148", "type 2 diabetes"),
    ]
    out = extract_neighborhood(rows, _MONDO)
    comp = out["type2_diabetes"]["complications"]
    assert "chronic kidney disease" in comp  # 정방향(당뇨→ckd)
    assert "cardiovascular disease" in comp  # 역방향(cvd→당뇨)


def test_phenotype_collected_from_disease_x_side() -> None:
    rows = [
        _row(
            "disease_phenotype_positive",
            "5148",
            "type 2 diabetes",
            "HP1",
            "Insulin resistance",
            yt="effect/phenotype",
        )
    ]
    out = extract_neighborhood(rows, _MONDO)
    assert out["type2_diabetes"]["phenotypes"] == ["Insulin resistance"]


def test_exposure_collected_from_disease_y_side() -> None:
    rows = [
        _row(
            "exposure_disease",
            "EXP1",
            "Air Pollutants",
            "5148",
            "type 2 diabetes",
            xt="exposure",
        )
    ]
    out = extract_neighborhood(rows, _MONDO)
    assert out["type2_diabetes"]["exposures"] == ["Air Pollutants"]


def test_deduplicates_case_insensitive() -> None:
    rows = [
        _row(
            "disease_phenotype_positive",
            "5148",
            "t2d",
            "H1",
            "Insulin Resistance",
            yt="effect/phenotype",
        ),
        _row(
            "disease_phenotype_positive",
            "5148",
            "t2d",
            "H2",
            "insulin resistance",
            yt="effect/phenotype",
        ),
    ]
    out = extract_neighborhood(rows, _MONDO)
    assert out["type2_diabetes"]["phenotypes"] == ["Insulin Resistance"]  # 첫 등장만


def test_caps_bucket_size() -> None:
    rows = [
        _row(
            "disease_phenotype_positive",
            "5148",
            "t2d",
            f"H{i}",
            f"pheno{i:03d}",
            yt="effect/phenotype",
        )
        for i in range(50)
    ]
    out = extract_neighborhood(rows, _MONDO, cap=25)
    assert len(out["type2_diabetes"]["phenotypes"]) == 25


def test_ignores_unrelated_relations_and_unmapped_ids() -> None:
    rows = [
        _row("drug_drug", "D1", "drugA", "D2", "drugB", xt="drug", yt="drug"),
        _row("disease_disease", "99999", "unmapped disease", "88888", "other"),
    ]
    assert extract_neighborhood(rows, _MONDO) == {}


def test_type_guard_blocks_id_collision_across_node_types() -> None:
    # 노출 노드가 우연히 질환 mondo id와 같은 문자열을 가져도, 타입이 disease가 아니면 무시.
    rows = [
        _row("exposure_disease", "5148", "not a disease", "X", "irrelevant", xt="exposure", yt="disease"),
    ]
    out = extract_neighborhood(rows, _MONDO)
    # y가 매핑 안 된 'X'라 아무것도 안 담긴다(x의 5148은 exposure 타입이라 조건으로 안 봄).
    assert out == {}
