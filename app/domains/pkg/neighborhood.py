"""조건별 외부 의학 KG 이웃(사실) — 추출 코어 + committed 시드 로더.

외부 의학 KG(PrimeKG)에서 조건별로 합병증(disease_disease)·증상(disease_phenotype_positive)·
노출인자(exposure_disease)를 뽑아둔 정적 시드(condition_neighborhood.json)를 읽는다. 이 시드는
scripts/extract_condition_neighborhood.py가 kg.csv에서 오프라인 생성한다 — 런타임은 원본
982MB kg.csv에 의존하지 않고 committed 시드만 쓴다.

목적: LLM에 "의학적 내용"(증상·합병증·노출)을 grounding으로 먹여, 안 뻔하고 개인화된 미션을
생성하기 위한 재료. 생활수칙으로의 번역은 LLM 몫(관계 자체는 생활수칙일 필요 없음).
"""

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

# PrimeKG relation → 시드 버킷.
_RELATION_BUCKET: dict[str, str] = {
    "disease_disease": "complications",
    "disease_phenotype_positive": "phenotypes",
    "exposure_disease": "exposures",
}
_BUCKETS = ("complications", "phenotypes", "exposures")
_DEFAULT_CAP = 25  # 조건·버킷당 최대 항목(시드 크기 억제)

_DATA_PATH = Path(__file__).parent / "data" / "condition_neighborhood.json"

# kg.csv row 튜플: (relation, x_id, x_type, x_name, y_id, y_type, y_name)
KgRow = tuple[str, str, str, str, str, str, str]


def extract_neighborhood(
    rows: Iterable[KgRow],
    mondo_map: dict[str, str],
    *,
    cap: int = _DEFAULT_CAP,
) -> dict[str, dict[str, list[str]]]:
    """KG 행 시퀀스 → 조건별 {complications/phenotypes/exposures: [이웃명]}.

    disease_disease는 조건이 어느 endpoint든 반대쪽 질환명을, disease_phenotype_positive는
    질환(x)의 증상(y)을, exposure_disease는 질환(y)의 노출인자(x)를 담는다. 대소문자 무관
    중복 제거, 버킷당 cap개까지. 빈 조건은 결과에서 생략한다.
    """
    id_to_cond = {mondo: cond for cond, mondo in mondo_map.items()}
    buckets: dict[str, dict[str, list[str]]] = {
        cond: {b: [] for b in _BUCKETS} for cond in mondo_map
    }
    seen: dict[str, dict[str, set[str]]] = {
        cond: {b: set() for b in _BUCKETS} for cond in mondo_map
    }

    def add(cond: str, bucket: str, name: str) -> None:
        clean = name.strip()
        key = clean.lower()
        if not key or key in seen[cond][bucket] or len(buckets[cond][bucket]) >= cap:
            return
        seen[cond][bucket].add(key)
        buckets[cond][bucket].append(clean)

    for relation, x_id, x_type, x_name, y_id, y_type, y_name in rows:
        bucket = _RELATION_BUCKET.get(relation)
        if bucket is None:
            continue
        if relation == "disease_disease":
            if x_type == "disease" and x_id in id_to_cond:
                add(id_to_cond[x_id], bucket, y_name)
            if y_type == "disease" and y_id in id_to_cond:
                add(id_to_cond[y_id], bucket, x_name)
        elif relation == "disease_phenotype_positive":
            if x_type == "disease" and x_id in id_to_cond:
                add(id_to_cond[x_id], bucket, y_name)
        elif relation == "exposure_disease":
            if y_type == "disease" and y_id in id_to_cond:
                add(id_to_cond[y_id], bucket, x_name)

    result: dict[str, dict[str, list[str]]] = {}
    for cond, b in buckets.items():
        entry = {name: sorted(vals, key=str.lower) for name, vals in b.items() if vals}
        if entry:
            result[cond] = entry
    return result


@lru_cache(maxsize=1)
def load_neighborhood() -> dict:
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def condition_facts(conditions: list[str]) -> dict[str, dict[str, list[str]]]:
    """유저 조건에 해당하는 KG 이웃 사실만 추린다(시드에 없는 조건은 생략).

    lru_cache된 원본을 호출자가 수정해도 캐시가 오염되지 않도록 버킷·리스트까지 복사한다.
    """
    data = load_neighborhood().get("conditions", {})
    return {
        c: {bucket: list(facts) for bucket, facts in data[c].items()}
        for c in conditions
        if c in data
    }


_CURATION_PER_CONDITION = 4


def deterministic_curation(
    conditions: list[str], *, per_condition: int = _CURATION_PER_CONDITION
) -> list[str]:
    """원시 KG 이웃 → 결정론적 임상 요약(LLM 없을 때의 폴백/기본값).

    phenotypes(증상·징후, 신뢰도 높음)를 우선하고 complications(합병증)로 보조한다. 노이즈가
    많은 exposures(환경 독성물질)는 제외한다. 조건당 per_condition개까지.
    """
    facts: list[str] = []
    for cond, buckets in condition_facts(conditions).items():
        picks = (buckets.get("phenotypes", []) + buckets.get("complications", []))[:per_condition]
        facts.extend(f"{cond}: {name}" for name in picks)
    return facts
