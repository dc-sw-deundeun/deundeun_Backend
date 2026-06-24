"""Step 2: PrimeKG kg.csv에서 한국 일반건강검진 finding의 MONDO ID 후보를 출력한다.

검색 대상 finding/키워드는 kg/mappings/mapping_table.json을 단일 소스로 읽는다.
출력 결과를 직접 검토해 mapping_table.json의 각 finding mondo_id를 확정한다.
(추정값 사용 금지 — 반드시 CSV에서 확인한 값만 사용)

사용:
    python kg/scripts/01_inspect_diseases.py [kg.csv 경로]
"""

from __future__ import annotations

import json
import sys

import pandas as pd

from _common import KG_CSV, MAPPING_TABLE

CHUNK = 500_000


def load_findings() -> list[dict]:
    with open(MAPPING_TABLE, encoding="utf-8") as f:
        return json.load(f)["mappings"]


def collect_disease_nodes(path) -> pd.DataFrame:
    """kg.csv의 x/y 양쪽에서 disease 노드를 모아 (mondo_id, name, source)로 반환."""
    cols = [
        "x_type", "x_id", "x_name", "x_source",
        "y_type", "y_id", "y_name", "y_source",
    ]
    frames: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, usecols=cols, dtype=str, chunksize=CHUNK):
        for side in ("x", "y"):
            sub = chunk[chunk[f"{side}_type"] == "disease"][
                [f"{side}_id", f"{side}_name", f"{side}_source"]
            ]
            sub.columns = ["mondo_id", "name", "source"]
            frames.append(sub)
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else KG_CSV
    findings = load_findings()
    print(f"[load] {path}")
    diseases = collect_disease_nodes(path)
    print(f"[info] 고유 disease 노드: {len(diseases):,}개")
    print(f"[info] 매핑 대상 finding: {len(findings)}개\n")

    for item in findings:
        kws = item["keywords"]
        mask = pd.Series(False, index=diseases.index)
        for kw in kws:
            mask = mask | diseases["name"].str.contains(kw, case=False, na=False)
        result = diseases[mask].sort_values("name")
        header = f"=== [{item['category']}] {item['finding_ko']} ({item['finding_en']})"
        print(f"{header}  | keywords: {', '.join(kws)} ===")
        if result.empty:
            print("  (검색 결과 없음 — keywords 조정 필요)\n")
        else:
            print(result.to_string(index=False))
            print()


if __name__ == "__main__":
    main()
