"""Step 7: 식약처 DUR API로 안전 레이어를 추가한다.

- 병용금기 → (:Drug)-[:CONTRAINDICATED_WITH {source:'DUR', content}]->(:Drug)
- 연령(소아)금기 → Drug.age_contraindication = true (+_content)
- 임부금기 → Drug.pregnancy_contraindication = true (+_content)

품목기준코드(ITEM_SEQ) → ATC 변환은 hira_atc.csv(04 산출물)를 사용하고,
ATC → Drug 노드 매칭은 Drug.atc_codes 리스트로 한다.

주의: DUR API의 operation 이름/필드명은 공공데이터포털 스펙·발급 키에 따라 다를 수 있다.
      실행 전 OPERATIONS와 필드 상수를 실제 응답으로 검증할 것.

사용:
    python kg/scripts/06_dur_enrichment.py [hira_atc.csv]
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests

from _common import DUR_API_KEY, DUR_BASE_URL, HIRA_ATC_CSV, get_driver

BATCH = 2000
NUM_OF_ROWS = 100

# 공공데이터포털 DURPrdlstInfoService 오퍼레이션 (스펙 확인 후 보정)
OPERATIONS = {
    "usjnt": "getUsjntTabooInfoList03",   # 병용금기
    "age": "getOdsnAtentInfoList03",      # 노인/연령주의
    "preg": "getPwnmTabooInfoList03",     # 임부금기
}

# 응답 필드명 (스펙 확인 후 보정)
F_ITEM_SEQ = "ITEM_SEQ"
F_MIXTURE_ITEM_SEQ = "MIXTURE_ITEM_SEQ"
F_CONTENT = "PROHBT_CONTENT"


def chunked(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def load_item_atc(path: Path) -> dict[str, set[str]]:
    if not Path(path).exists():
        raise SystemExit(f"{path} 없음 — 먼저 04_hira_atc.py 실행")
    df = pd.read_csv(path, dtype=str)
    item_atc: dict[str, set[str]] = defaultdict(set)
    for item_seq, atc in zip(df["item_seq"], df["atc_code"]):
        if pd.notna(item_seq) and pd.notna(atc):
            item_atc[str(item_seq).strip()].add(atc)
    print(f"[hira] 품목기준코드 {len(item_atc):,}개 → ATC 매핑 로드")
    return item_atc


def fetch_all(operation: str) -> list[dict]:
    if not DUR_API_KEY:
        raise SystemExit("DUR_API_KEY 미설정 (.env)")
    url = f"{DUR_BASE_URL}/{operation}"
    rows: list[dict] = []
    page = 1
    while True:
        params = {
            "serviceKey": DUR_API_KEY,
            "type": "json",
            "pageNo": page,
            "numOfRows": NUM_OF_ROWS,
        }
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        body = (resp.json().get("body") or {})
        items = body.get("items") or []
        if isinstance(items, dict):  # {"item": [...]} 또는 단일 dict 대응
            items = items.get("item", items)
        if isinstance(items, dict):
            items = [items]
        rows.extend(items)
        total = int(body.get("totalCount", 0) or 0)
        if not items or page * NUM_OF_ROWS >= total:
            break
        page += 1
    print(f"[fetch] {operation}: {len(rows):,}건")
    return rows


def load_usjnt(driver, item_atc, rows) -> int:
    pairs = []
    for it in rows:
        a = str(it.get(F_ITEM_SEQ, "")).strip()
        b = str(it.get(F_MIXTURE_ITEM_SEQ, "")).strip()
        atc_a, atc_b = item_atc.get(a), item_atc.get(b)
        if atc_a and atc_b:
            pairs.append({"a": list(atc_a), "b": list(atc_b), "content": it.get(F_CONTENT, "")})
    merged = 0
    for batch in chunked(pairs, BATCH):
        driver.execute_query(
            "UNWIND $rows AS r "
            "MATCH (a:Drug) WHERE any(x IN a.atc_codes WHERE x IN r.a) "
            "MATCH (b:Drug) WHERE any(x IN b.atc_codes WHERE x IN r.b) "
            "MERGE (a)-[c:CONTRAINDICATED_WITH]->(b) "
            "SET c.source = 'DUR', c.content = r.content",
            rows=batch, database_="neo4j",
        )
        merged += len(batch)
    print(f"[병용금기] 매칭 페어 {merged:,}건 적재")
    return merged


def load_property(driver, item_atc, rows, prop: str) -> int:
    updates = []
    for it in rows:
        a = str(it.get(F_ITEM_SEQ, "")).strip()
        atcs = item_atc.get(a)
        if atcs:
            updates.append({"atc": list(atcs), "content": it.get(F_CONTENT, "")})
    for batch in chunked(updates, BATCH):
        driver.execute_query(
            "UNWIND $rows AS r "
            "MATCH (d:Drug) WHERE any(x IN d.atc_codes WHERE x IN r.atc) "
            f"SET d.{prop} = true, d.{prop}_content = r.content",
            rows=batch, database_="neo4j",
        )
    print(f"[{prop}] {len(updates):,}건 프로퍼티 적용")
    return len(updates)


def main() -> None:
    hira = Path(sys.argv[1]) if len(sys.argv) > 1 else HIRA_ATC_CSV
    item_atc = load_item_atc(hira)

    driver = get_driver()
    try:
        driver.verify_connectivity()
        load_usjnt(driver, item_atc, fetch_all(OPERATIONS["usjnt"]))
        load_property(driver, item_atc, fetch_all(OPERATIONS["age"]), "age_contraindication")
        load_property(driver, item_atc, fetch_all(OPERATIONS["preg"]), "pregnancy_contraindication")
        print("[done] DUR 안전 레이어 적재 완료")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
