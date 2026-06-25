"""Step 6: 식약처 DUR 안전 레이어를 CSV(공공데이터포털 파일데이터)로 적재한다.

API(DUR_API_KEY) 대신 data.go.kr에서 받은 DUR 품목 리스트 CSV(cp949)를 직접 읽는다.
파일데이터는 API와 동일한 데이터라 키 발급/호출제한이 없다 → DUR_API_KEY 불필요.

- 병용금기  → (:Drug)-[:CONTRAINDICATED_WITH {source:'DUR', content}]->(:Drug)
- 연령금기  → Drug.age_contraindication = true (+_content)
- 임부금기  → Drug.pregnancy_contraindication = true (+_content, +_grade)
- 노인주의  → Drug.elderly_caution = true (+_content)

조인: DUR 제품코드 → hira_atc.csv(04 산출물, item_seq=제품코드) → atc_code → Drug.atc_codes
      제품코드로 못 찾으면 성분코드 → main_ingr_code 로 폴백.
      제품 행이 수백만이라 ATC 집합 기준으로 dedup 후 적재한다.

사용:
    python kg/scripts/06_dur_enrichment.py [DUR_CSV_DIR] [hira_atc.csv]
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

from _common import DATA_DIR, HIRA_ATC_CSV, get_driver

BATCH = 2000
CHUNKSIZE = 100_000

# 공공데이터포털에서 받은 DUR 품목 리스트 CSV 폴더 (필요 시 argv[1]로 교체)
DUR_DIR_DEFAULT = DATA_DIR / "건강보험심사평가원_의약품안전사용서비스(DUR) 의약품 목록_202606"

# 파일명 키워드 (배포월이 바뀌어도 키워드로 찾는다)
KW_USJNT = "병용금기"
KW_AGE = "연령금기"
KW_PREG = "임부금기"
KW_ELDERLY = "노인주의"  # 일반 + 해열진통소염제 2개 파일

# DUR CSV 공통 컬럼
C_PRODUCT = "제품코드"
C_INGR = "성분코드"
C_CONTENT = "상세정보"        # 병용/연령/임부
C_CONTENT_ELDERLY = "약품상세정보"  # 노인주의
C_GRADE = "금기등급"          # 임부금기


def chunked(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def find_csvs(d: Path, keyword: str) -> list[Path]:
    matches = sorted(p for p in d.glob("*.csv") if keyword in p.name)
    if not matches:
        raise SystemExit(f"'{keyword}' 포함 CSV를 {d} 에서 못 찾음")
    return matches


def detect_encoding(path: Path) -> str:
    for enc in ("cp949", "utf-8-sig"):
        try:
            with open(path, encoding=enc) as fh:
                fh.readline()
            return enc
        except UnicodeDecodeError:
            continue
    return "cp949"


def iter_rows(path: Path):
    """대용량(병용금기 254MB) 대응으로 청크 스트리밍하며 dict 행을 yield."""
    enc = detect_encoding(path)
    for chunk in pd.read_csv(path, dtype=str, encoding=enc, chunksize=CHUNKSIZE):
        for rec in chunk.fillna("").to_dict("records"):
            yield rec


def load_item_atc(path: Path) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    if not Path(path).exists():
        raise SystemExit(f"{path} 없음 — 먼저 04_hira_atc.py 실행")
    df = pd.read_csv(path, dtype=str)
    by_product: dict[str, set[str]] = defaultdict(set)
    by_ingr: dict[str, set[str]] = defaultdict(set)
    for prod, ingr, atc in zip(df["item_seq"], df["main_ingr_code"], df["atc_code"]):
        if pd.isna(atc) or not str(atc).strip():
            continue
        if pd.notna(prod) and str(prod).strip():
            by_product[str(prod).strip()].add(str(atc).strip())
        if pd.notna(ingr) and str(ingr).strip():
            by_ingr[str(ingr).strip()].add(str(atc).strip())
    print(f"[hira] 제품코드 {len(by_product):,} / 성분코드 {len(by_ingr):,} → ATC 매핑 로드")
    return by_product, by_ingr


def lookup_atc(by_product, by_ingr, product_code: str, ingr_code: str) -> set[str]:
    pc = str(product_code).strip()
    if pc and pc in by_product:
        return by_product[pc]
    ic = str(ingr_code).strip()
    if ic and ic in by_ingr:
        return by_ingr[ic]
    return set()


def load_usjnt(driver, by_product, by_ingr, paths: list[Path]) -> int:
    # (ATC_A 집합, ATC_B 집합) 기준으로 dedup — 수백만 제품 행을 ATC 페어로 축약
    seen: dict[tuple, str] = {}
    for path in paths:
        for row in iter_rows(path):
            atc_a = frozenset(lookup_atc(by_product, by_ingr, row.get(f"{C_PRODUCT}A", ""), row.get(f"{C_INGR}A", "")))
            atc_b = frozenset(lookup_atc(by_product, by_ingr, row.get(f"{C_PRODUCT}B", ""), row.get(f"{C_INGR}B", "")))
            if atc_a and atc_b:
                seen.setdefault((atc_a, atc_b), row.get(C_CONTENT, ""))
    pairs = [{"a": list(a), "b": list(b), "content": c} for (a, b), c in seen.items()]
    matched = 0
    for batch in chunked(pairs, BATCH):
        recs, _, _ = driver.execute_query(
            "UNWIND $rows AS r "
            "MATCH (a:Drug) WHERE any(x IN a.atc_codes WHERE x IN r.a) "
            "MATCH (b:Drug) WHERE any(x IN b.atc_codes WHERE x IN r.b) "
            "MERGE (a)-[c:CONTRAINDICATED_WITH]->(b) "
            "SET c.source = 'DUR', c.content = r.content "
            "RETURN count(*) AS c",
            rows=batch, database_="neo4j",
        )
        matched += recs[0]["c"]
    print(f"[병용금기] 엣지 쓰기 {matched:,}건 (보낸 ATC 페어 {len(pairs):,})")
    return matched


def load_property(driver, by_product, by_ingr, paths: list[Path], prop: str,
                  content_col: str, extra: dict[str, str] | None = None) -> int:
    extra = extra or {}
    # ATC 집합 기준으로 dedup
    seen: dict[frozenset, dict] = {}
    for path in paths:
        for row in iter_rows(path):
            atcs = frozenset(lookup_atc(by_product, by_ingr, row.get(C_PRODUCT, ""), row.get(C_INGR, "")))
            if not atcs:
                continue
            if atcs not in seen:
                rec = {"content": row.get(content_col, "")}
                for k, col in extra.items():
                    rec[k] = row.get(col, "")
                seen[atcs] = rec

    set_clause = f"SET d.{prop} = true, d.{prop}_content = r.content" + "".join(
        f", d.{prop}_{k} = r.{k}" for k in extra
    )
    updates = [{"atc": list(atcs), **rec} for atcs, rec in seen.items()]
    matched = 0
    for batch in chunked(updates, BATCH):
        recs, _, _ = driver.execute_query(
            "UNWIND $rows AS r "
            "MATCH (d:Drug) WHERE any(x IN d.atc_codes WHERE x IN r.atc) "
            + set_clause + " RETURN count(d) AS c",
            rows=batch, database_="neo4j",
        )
        matched += recs[0]["c"]
    print(f"[{prop}] {matched:,}건 적용 (보낸 ATC 집합 {len(updates):,})")
    return matched


def main() -> None:
    dur_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DUR_DIR_DEFAULT
    hira = Path(sys.argv[2]) if len(sys.argv) > 2 else HIRA_ATC_CSV
    if not dur_dir.exists():
        raise SystemExit(f"DUR CSV 폴더 없음: {dur_dir}")

    by_product, by_ingr = load_item_atc(hira)

    driver = get_driver()
    try:
        driver.verify_connectivity()
        load_usjnt(driver, by_product, by_ingr, find_csvs(dur_dir, KW_USJNT))
        load_property(driver, by_product, by_ingr, find_csvs(dur_dir, KW_AGE),
                      "age_contraindication", C_CONTENT)
        load_property(driver, by_product, by_ingr, find_csvs(dur_dir, KW_PREG),
                      "pregnancy_contraindication", C_CONTENT, extra={"grade": C_GRADE})
        load_property(driver, by_product, by_ingr, find_csvs(dur_dir, KW_ELDERLY),
                      "elderly_caution", C_CONTENT_ELDERLY)
        print("[done] DUR 안전 레이어 적재 완료")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
