"""Step 6: kg_clinical.csv를 Neo4j에 MERGE 적재한다.

- cypher/schema.cypher의 제약/인덱스를 먼저 적용
- 노드 MERGE: (:Disease {mondo_id,name,source}), (:Drug {drugbank_id,name,atc_code,atc_codes,source}),
  (:Effect {hpo_id,name,source})  — Drug는 drugbank_atc.csv로 ATC 부여
- 엣지 MERGE: (x)-[:RELATION {type, source}]->(y)  (type=display_relation)

접속정보는 .env(NEO4J_URI/USER/PASSWORD)에서 읽는다.

사용:
    python kg/scripts/05_load_neo4j.py [kg_clinical.csv] [drugbank_atc.csv]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from _common import DRUGBANK_ATC_CSV, KG_CLINICAL_CSV, KG_DIR, get_driver

SCHEMA_CYPHER = KG_DIR / "cypher" / "schema.cypher"
BATCH = 5000
READ_CHUNK = 200_000

# x_type/y_type -> (Neo4j 라벨, 키 프로퍼티)
TYPE_MAP = {
    "disease": ("Disease", "mondo_id"),
    "drug": ("Drug", "drugbank_id"),
    "effect/phenotype": ("Effect", "hpo_id"),
}


def chunked(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def run_schema(driver) -> None:
    raw = SCHEMA_CYPHER.read_text(encoding="utf-8")
    body = "\n".join(ln for ln in raw.splitlines() if not ln.strip().startswith("//"))
    stmts = [s.strip() for s in body.split(";") if s.strip()]
    for stmt in stmts:
        driver.execute_query(stmt, database_="neo4j")
    print(f"[schema] {len(stmts)}개 제약/인덱스 적용")


def load_atc_map(path: Path) -> dict[str, list[str]]:
    if not Path(path).exists():
        print(f"[warn] {path} 없음 — Drug ATC 미부여")
        return {}
    df = pd.read_csv(path, dtype=str)
    atc_map: dict[str, list[str]] = {}
    for db_id, grp in df.groupby("drugbank_id"):
        codes = sorted({c for c in grp["atc_code"] if pd.notna(c)})
        if codes:
            atc_map[db_id] = codes
    print(f"[atc] {len(atc_map):,}개 약물에 ATC 매핑 로드")
    return atc_map


def collect_nodes(csv_path: Path) -> dict[str, dict[str, str]]:
    nodes: dict[str, dict[str, str]] = {t: {} for t in TYPE_MAP}
    cols = ["x_type", "x_id", "x_name", "y_type", "y_id", "y_name"]
    for chunk in pd.read_csv(csv_path, usecols=cols, dtype=str, chunksize=READ_CHUNK):
        for side in ("x", "y"):
            for t in TYPE_MAP:
                sub = chunk[chunk[f"{side}_type"] == t]
                nodes[t].update(zip(sub[f"{side}_id"], sub[f"{side}_name"]))
    nodes = {t: {i: n for i, n in d.items() if pd.notna(i)} for t, d in nodes.items()}
    return nodes


def merge_nodes(driver, nodes: dict[str, dict[str, str]], atc_map: dict[str, list[str]]) -> None:
    disease_rows = [{"id": i, "name": n} for i, n in nodes["disease"].items()]
    for batch in chunked(disease_rows, BATCH):
        driver.execute_query(
            "UNWIND $rows AS r MERGE (d:Disease {mondo_id: r.id}) "
            "SET d.name = r.name, d.source = 'PrimeKG'",
            rows=batch, database_="neo4j",
        )

    drug_rows = []
    for i, n in nodes["drug"].items():
        codes = atc_map.get(i, [])
        drug_rows.append(
            {"id": i, "name": n, "atc_codes": codes, "atc_code": codes[0] if codes else None}
        )
    for batch in chunked(drug_rows, BATCH):
        driver.execute_query(
            "UNWIND $rows AS r MERGE (d:Drug {drugbank_id: r.id}) "
            "SET d.name = r.name, d.source = 'PrimeKG', "
            "d.atc_codes = r.atc_codes, d.atc_code = r.atc_code",
            rows=batch, database_="neo4j",
        )

    effect_rows = [{"id": i, "name": n} for i, n in nodes["effect/phenotype"].items()]
    for batch in chunked(effect_rows, BATCH):
        driver.execute_query(
            "UNWIND $rows AS r MERGE (e:Effect {hpo_id: r.id}) "
            "SET e.name = r.name, e.source = 'PrimeKG'",
            rows=batch, database_="neo4j",
        )

    print(
        f"[nodes] Disease {len(disease_rows):,} / "
        f"Drug {len(drug_rows):,} / Effect {len(effect_rows):,}"
    )


def merge_edges(driver, csv_path: Path) -> None:
    cols = ["x_type", "x_id", "y_type", "y_id", "display_relation"]
    total = 0
    for chunk in pd.read_csv(csv_path, usecols=cols, dtype=str, chunksize=READ_CHUNK):
        chunk = chunk[chunk["x_type"].isin(TYPE_MAP) & chunk["y_type"].isin(TYPE_MAP)]
        for (xt, yt), grp in chunk.groupby(["x_type", "y_type"]):
            xl, xk = TYPE_MAP[xt]
            yl, yk = TYPE_MAP[yt]
            query = (
                "UNWIND $rows AS row "
                f"MATCH (x:{xl} {{{xk}: row.x}}) "
                f"MATCH (y:{yl} {{{yk}: row.y}}) "
                "MERGE (x)-[rel:RELATION {type: row.rel}]->(y) "
                "SET rel.source = 'PrimeKG'"
            )
            rows = [
                {"x": r.x_id, "y": r.y_id, "rel": r.display_relation}
                for r in grp.itertuples(index=False)
            ]
            for batch in chunked(rows, BATCH):
                driver.execute_query(query, rows=batch, database_="neo4j")
                total += len(batch)
        print(f"  edges 누적 {total:,}")
    print(f"[edges] 총 {total:,}")


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else KG_CLINICAL_CSV
    atc_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DRUGBANK_ATC_CSV
    if not Path(csv_path).exists():
        raise SystemExit(f"입력 없음: {csv_path} (먼저 02_filter_primekg.py 실행)")

    driver = get_driver()
    try:
        driver.verify_connectivity()
        print("[load] kg_clinical →", csv_path)
        run_schema(driver)
        nodes = collect_nodes(csv_path)
        merge_nodes(driver, nodes, load_atc_map(atc_path))
        merge_edges(driver, csv_path)
        print("[done] 적재 완료")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
