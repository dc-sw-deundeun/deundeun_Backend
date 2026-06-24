"""Step 7b: 약물-식품(DDID) 상호작용 엣지를 적재한다.

데이터 소스 미확정(별도 확보 필요). 확보한 데이터를 아래 컬럼의 CSV로 정리해 입력하면
(:Drug)-[:FOOD_INTERACTION {effect, severity, source}]->(:Food) 로 적재한다.

입력 CSV 컬럼: atc_code, food, effect, severity[, source]
  - atc_code 기준으로 Drug.atc_codes 와 매칭

사용:
    python kg/scripts/07_food_interaction.py <food_interactions.csv>
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from _common import get_driver

BATCH = 2000


def chunked(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = Path(sys.argv[1])
    if not src.exists():
        raise SystemExit(f"입력 없음: {src}")

    df = pd.read_csv(src, dtype=str).fillna("")
    required = {"atc_code", "food", "effect"}
    if not required.issubset(df.columns):
        raise SystemExit(f"필수 컬럼 {required} 누락. 실제: {list(df.columns)}")

    rows = [
        {
            "atc": r["atc_code"].strip(),
            "food": r["food"].strip(),
            "effect": r.get("effect", ""),
            "severity": r.get("severity", ""),
            "source": r.get("source", "") or "DDID",
        }
        for _, r in df.iterrows()
        if r["atc_code"].strip() and r["food"].strip()
    ]

    driver = get_driver()
    try:
        driver.verify_connectivity()
        driver.execute_query(
            "CREATE CONSTRAINT food_name IF NOT EXISTS "
            "FOR (f:Food) REQUIRE f.name IS UNIQUE",
            database_="neo4j",
        )
        loaded = 0
        for batch in chunked(rows, BATCH):
            driver.execute_query(
                "UNWIND $rows AS r "
                "MATCH (d:Drug) WHERE r.atc IN d.atc_codes "
                "MERGE (f:Food {name: r.food}) "
                "MERGE (d)-[fi:FOOD_INTERACTION {effect: r.effect}]->(f) "
                "SET fi.severity = r.severity, fi.source = r.source",
                rows=batch, database_="neo4j",
            )
            loaded += len(batch)
        print(f"[food] {loaded:,}건 약물-식품 상호작용 적재")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
