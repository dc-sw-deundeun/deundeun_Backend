"""condition_neighborhood.json 시드 구조 유효성 + 로더(condition_facts).

시드는 scripts/extract_condition_neighborhood.py가 kg.csv에서 생성한 committed 산출물.
여기선 원본 kg.csv 없이 committed 시드의 형태와 로더 동작만 검증한다(CI 안전).
"""

from app.domains.pkg.neighborhood import condition_facts, load_neighborhood

_BUCKETS = {"complications", "phenotypes", "exposures"}


def test_seed_has_conditions_with_valid_structure() -> None:
    data = load_neighborhood()
    assert "conditions" in data
    conds = data["conditions"]
    assert conds  # 비어있지 않음
    for cond, entry in conds.items():
        assert set(entry).issubset(_BUCKETS), f"{cond}: 알 수 없는 버킷 {set(entry)}"
        for bucket, vals in entry.items():
            assert isinstance(vals, list) and vals, f"{cond}.{bucket}: 빈/비리스트"
            assert all(isinstance(v, str) and v.strip() for v in vals)


def test_key_conditions_present_and_nonempty() -> None:
    conds = load_neighborhood()["conditions"]
    for c in ("type2_diabetes", "obesity", "hypertension"):
        assert c in conds and conds[c], f"{c}: 시드 없음/빈값"


def test_condition_facts_filters_to_user_conditions() -> None:
    facts = condition_facts(["type2_diabetes", "nonexistent_condition"])
    assert "type2_diabetes" in facts
    assert "nonexistent_condition" not in facts


def test_condition_facts_empty_for_unmapped_conditions() -> None:
    # insomnia·gerd는 condition_mondo_map에 없어 시드에도 없다.
    assert condition_facts(["insomnia", "gerd"]) == {}
