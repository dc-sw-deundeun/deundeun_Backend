"""Step 4-b: DrugBank 라이선스 없이 Drug↔ATC 매핑을 만든다 (name-bridge).

DrugBank full XML(03)을 못 구할 때의 우회로. 심평원 ATC 매핑(hira_atc.csv)에는
`atc_name`(영문 성분명, 예: "chloral hydrate")이 있고, PrimeKG Drug 노드 이름도
영문 성분명(INN)이라, 정규화한 이름으로 조인해 ATC를 부여한다.

- 입력: hira_atc.csv(04 산출물), kg_clinical.csv(02 산출물에서 Drug 이름 추출)
- 출력: drugbank_atc.csv (컬럼: drugbank_id, name, atc_code) — 03과 동일 포맷이라 05가 그대로 적재

한계: 정확 일치 기준이라 한국 미유통/표기변형 약물은 누락된다(전체의 일부만 커버).
      추후 DrugBank XML을 받으면 03으로 교체해 커버리지를 끌어올린다.

사용:
    python kg/scripts/03b_namebridge_atc.py [hira_atc.csv] [kg_clinical.csv] [출력.csv]
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

from _common import DRUGBANK_ATC_CSV, HIRA_ATC_CSV, KG_CLINICAL_CSV

READ_CHUNK = 200_000


def norm(s) -> str:
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def load_name2atc(hira_path: Path) -> dict[str, set[str]]:
    df = pd.read_csv(hira_path, dtype=str)
    name2atc: dict[str, set[str]] = defaultdict(set)
    for nm, code in zip(df["atc_name"], df["atc_code"]):
        n = norm(nm)
        if n and isinstance(code, str) and code.strip():
            name2atc[n].add(code.strip())
    print(f"[hira] 영문 성분명(atc_name) {len(name2atc):,}개 → ATC 매핑")
    return name2atc


def load_drug_names(kg_clinical_path: Path) -> dict[str, str]:
    """kg_clinical.csv에서 drugbank_id → 영문 이름을 모은다."""
    names: dict[str, str] = {}
    cols = ["x_type", "x_id", "x_name", "y_type", "y_id", "y_name"]
    for chunk in pd.read_csv(kg_clinical_path, usecols=cols, dtype=str, chunksize=READ_CHUNK):
        for side in ("x", "y"):
            sub = chunk[chunk[f"{side}_type"] == "drug"]
            for i, n in zip(sub[f"{side}_id"], sub[f"{side}_name"]):
                if pd.notna(i):
                    names[i] = n
    print(f"[kg] Drug 노드 {len(names):,}개 이름 로드")
    return names


def main() -> None:
    hira = Path(sys.argv[1]) if len(sys.argv) > 1 else HIRA_ATC_CSV
    kg = Path(sys.argv[2]) if len(sys.argv) > 2 else KG_CLINICAL_CSV
    dst = Path(sys.argv[3]) if len(sys.argv) > 3 else DRUGBANK_ATC_CSV
    for p in (hira, kg):
        if not Path(p).exists():
            raise SystemExit(f"입력 없음: {p}")

    name2atc = load_name2atc(hira)
    drug_names = load_drug_names(kg)

    rows = []
    matched = 0
    for db_id, name in drug_names.items():
        codes = name2atc.get(norm(name))
        if codes:
            matched += 1
            for code in sorted(codes):
                rows.append({"drugbank_id": db_id, "name": name, "atc_code": code})

    out = pd.DataFrame(rows, columns=["drugbank_id", "name", "atc_code"])
    out.to_csv(dst, index=False)
    total = len(drug_names)
    print(f"[match] {matched:,}/{total:,} Drug에 ATC 부여 ({100*matched/max(1,total):.0f}%)")
    print(f"[saved] {dst} ({len(out):,} rows)")


if __name__ == "__main__":
    main()
