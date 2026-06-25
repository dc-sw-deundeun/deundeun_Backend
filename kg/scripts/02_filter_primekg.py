"""Step 3: PrimeKG kg.csv를 임상 레이어로 필터링한다.

- 노드 prune: x_type, y_type 둘 다 {disease, drug, effect/phenotype} 인 엣지만 유지
- relation 필터: `relation` 컬럼(머신 이름) 화이트리스트만 유지 (display_relation 아님)
- 결과: kg/data/kg_clinical.csv + 노드/엣지/relation 카운트 리포트

drug_drug(약물 상호작용)는 제외 — 약물-약물 안전은 DUR 레이어(병용금기)로 커버한다.
off-label use, phenotype_phenotype(effect 계층)도 제외.

사용:
    python kg/scripts/02_filter_primekg.py [입력 kg.csv] [출력 kg_clinical.csv]
"""

from __future__ import annotations

import sys
from collections import Counter

import pandas as pd

from _common import KG_CLINICAL_CSV, KG_CSV

# x_type/y_type 유지 대상. 'effect/phenotype'는 PrimeKG의 실제 노드 타입 문자열.
# (실행 초반 출력되는 x_type 분포로 실제 문자열을 반드시 확인할 것)
KEEP_NODE_TYPES = {"disease", "drug", "effect/phenotype"}

# `relation` 컬럼(머신 이름) 유지 대상 — 앱 목적(치료/가드레일/고위험군/증상/부작용)에 맞춘 6종
KEEP_RELATIONS = {
    "indication",                   # Drug→Disease: 치료 적응증
    "contraindication",             # Drug→Disease: 안전 가드레일
    "disease_disease",              # Disease→Disease: 고위험군 판별
    "disease_phenotype_positive",   # Disease→Phenotype: 동반 증상 (해석 grounding)
    "disease_phenotype_negative",   # Disease→Phenotype: 배제 증상
    "drug_effect",                  # Drug→Phenotype: 약물 부작용
}

CHUNK = 500_000


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else KG_CSV
    dst = sys.argv[2] if len(sys.argv) > 2 else KG_CLINICAL_CSV

    node_sets: dict[str, set[str]] = {t: set() for t in KEEP_NODE_TYPES}
    rel_counter: Counter[str] = Counter()
    edge_total = 0
    header_written = False
    first_chunk = True

    print(f"[load] {src}")
    reader = pd.read_csv(src, dtype=str, chunksize=CHUNK, low_memory=False)
    for i, chunk in enumerate(reader):
        if first_chunk:
            print("[info] x_type 분포:", chunk["x_type"].value_counts().to_dict())
            print(
                "[info] relation 상위 20:",
                chunk["relation"].value_counts().head(20).to_dict(),
            )
            first_chunk = False

        filtered = chunk[
            chunk["x_type"].isin(KEEP_NODE_TYPES)
            & chunk["y_type"].isin(KEEP_NODE_TYPES)
            & chunk["relation"].isin(KEEP_RELATIONS)
        ]
        if filtered.empty:
            continue

        filtered.to_csv(
            dst,
            mode="a" if header_written else "w",
            header=not header_written,
            index=False,
        )
        header_written = True
        edge_total += len(filtered)
        rel_counter.update(filtered["relation"].tolist())

        for side in ("x", "y"):
            sub = filtered[[f"{side}_type", f"{side}_id"]].drop_duplicates()
            for node_type, grp in sub.groupby(f"{side}_type"):
                node_sets[node_type].update(grp[f"{side}_id"].tolist())

        print(f"  chunk {i}: 누적 엣지 {edge_total:,}")

    if not header_written:
        print("\n[경고] 필터 결과가 비었습니다. KEEP_NODE_TYPES / KEEP_RELATIONS 문자열을 "
              "위 x_type·relation 분포와 대조하세요.")
        return

    print("\n===== 필터링 리포트 =====")
    print(f"엣지 총합: {edge_total:,}")
    for node_type in sorted(node_sets):
        print(f"노드[{node_type}]: {len(node_sets[node_type]):,}")
    print("relation별 카운트:")
    for rel, count in rel_counter.most_common():
        print(f"  {rel}: {count:,}")
    print(f"\n[saved] {dst}")


if __name__ == "__main__":
    main()
