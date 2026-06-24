"""Step 9: 적재 결과를 검증하고 리포트를 출력한다.

- 노드 라벨별 / PrimeKG relation별 / 전체 관계 타입별 카운트
- mapping_table.json의 확정 MONDO ID가 그래프에 Disease로 존재하는지 확인
- 당뇨 멀티홉 샘플

사용:
    python kg/scripts/09_verify.py
"""

from __future__ import annotations

import json

from _common import MAPPING_TABLE, get_driver


def run(driver, cypher: str, **params):
    records, _, _ = driver.execute_query(cypher, database_="neo4j", **params)
    return records


def main() -> None:
    driver = get_driver()
    try:
        driver.verify_connectivity()

        print("== 노드 라벨별 카운트 ==")
        for r in run(driver, "MATCH (n) RETURN labels(n) AS labels, count(n) AS c ORDER BY c DESC"):
            print(f"  {r['labels']}: {r['c']:,}")

        print("\n== PrimeKG relation(type) 카운트 ==")
        for r in run(
            driver,
            "MATCH ()-[r:RELATION]->() RETURN r.type AS t, count(r) AS c ORDER BY c DESC",
        ):
            print(f"  {r['t']}: {r['c']:,}")

        print("\n== 전체 관계 타입 카운트 ==")
        for r in run(driver, "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY c DESC"):
            print(f"  {r['t']}: {r['c']:,}")

        print("\n== mapping_table MONDO 커버리지 ==")
        findings = json.loads(MAPPING_TABLE.read_text(encoding="utf-8"))["mappings"]
        confirmed = [m for m in findings if m.get("mondo_id")]
        found_cnt = 0
        for m in confirmed:
            rec = run(
                driver,
                "MATCH (d:Disease {mondo_id: $id}) RETURN count(d) AS c",
                id=m["mondo_id"],
            )
            ok = rec[0]["c"] > 0
            found_cnt += int(ok)
            print(f"  [{'OK' if ok else 'MISSING'}] {m['finding_ko']} -> {m['mondo_id']}")
        print(
            f"  확정 {len(confirmed)}개 중 그래프 존재 {found_cnt}개 / "
            f"미확정(null) {len(findings) - len(confirmed)}개"
        )

        print("\n== 당뇨 멀티홉 샘플 ==")
        for r in run(
            driver,
            "MATCH (d:Disease)-[r]-(n) WHERE toLower(d.name) CONTAINS 'diabetes' "
            "RETURN d.name AS dn, type(r) AS rt, r.type AS pt, labels(n) AS nl, n.name AS nn "
            "LIMIT 15",
        ):
            print(f"  {r['dn']} -[{r['rt']}/{r['pt']}]- {r['nl']} {r['nn']}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
