"""Step 10: 한국 미유통 약물을 골라내 KG를 한국 시장 전용으로 정리한다.

판별: Drug.atc_codes ∩ (한국 ATC 집합) ≠ ∅ → 한국 유통(kr_market=true), 아니면 false.
      한국 ATC 집합 = hira_atc.csv(04 산출물)의 atc_code 전체.

⚠️ 정확도 전제 (둘 다 충족해야 함):
  1) 모든 Drug에 ATC가 있어야 한다 → DrugBank full XML 기반 완전한 drugbank_atc.csv로
     05 재적재(또는 패치). 지금처럼 name-bridge 36%면 64%가 unknown으로 빠진다.
  2) hira_atc.csv가 완전한 한국 ATC 목록이어야 한다. 부분 목록이면 한국 출시약도 false가 됨
     (예: 구아이페네신). → 완전한 심평원/식약처 ATC 파일로 04 재실행 후 사용.

ATC가 아예 없는 Drug는 판별 불가(unknown) → 삭제하지 않고 보존하며 따로 보고한다.

2단계:
  1) 리뷰(기본, 삭제 안 함): 노드에 d.kr_market/d.market_status 태깅 + 삭제후보 CSV + 요약
       python kg/scripts/10_filter_korea.py [hira_atc.csv]
  2) 적용(삭제): 리뷰 확인 후 non-kr 약물 + 딸린 관계 DETACH DELETE
       python kg/scripts/10_filter_korea.py --apply [hira_atc.csv]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from _common import DATA_DIR, HIRA_ATC_CSV, get_driver

BATCH = 5000
DROP_REVIEW_CSV = DATA_DIR / "kr_filter_drop_candidates.csv"


def chunked(seq: list, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def load_kr_atc(path: Path) -> set[str]:
    if not Path(path).exists():
        raise SystemExit(f"{path} 없음 — 먼저 04_hira_atc.py 실행")
    df = pd.read_csv(path, dtype=str)
    codes = {str(c).strip() for c in df["atc_code"].dropna() if str(c).strip()}
    print(f"[kr] 한국 ATC 집합 {len(codes):,}개 (from {Path(path).name})")
    return codes


def classify_and_tag(driver, kr_atc: set[str]) -> dict[str, int]:
    """모든 Drug를 분류해 d.kr_market/d.market_status 로 태깅하고 삭제후보 CSV를 쓴다."""
    records, _, _ = driver.execute_query(
        "MATCH (d:Drug) RETURN d.drugbank_id AS id, d.name AS name, d.atc_codes AS atc",
        database_="neo4j",
    )
    updates, drop_rows = [], []
    counts = {"kr": 0, "non-kr": 0, "unknown": 0}
    for r in records:
        atc = r["atc"] or []
        if not atc:
            status = "unknown"
        elif any(a in kr_atc for a in atc):
            status = "kr"
        else:
            status = "non-kr"
            drop_rows.append(
                {"drugbank_id": r["id"], "name": r["name"], "atc_codes": ";".join(atc)}
            )
        counts[status] += 1
        updates.append({"id": r["id"], "kr": status == "kr", "status": status})

    for batch in chunked(updates, BATCH):
        driver.execute_query(
            "UNWIND $rows AS r MATCH (d:Drug {drugbank_id: r.id}) "
            "SET d.kr_market = r.kr, d.market_status = r.status",
            rows=batch, database_="neo4j",
        )

    pd.DataFrame(drop_rows, columns=["drugbank_id", "name", "atc_codes"]).to_csv(
        DROP_REVIEW_CSV, index=False
    )
    print(
        f"[tag] kr(유지)={counts['kr']:,} / non-kr(삭제후보)={counts['non-kr']:,} / "
        f"unknown(ATC없음·보존)={counts['unknown']:,}"
    )
    print(f"[review] 삭제후보 목록 → {DROP_REVIEW_CSV}")
    print("[sample] 삭제후보 일부:")
    for x in drop_rows[:15]:
        print(f"   - {x['name']}  [{x['atc_codes']}]")
    return counts


def apply_delete(driver) -> int:
    n = driver.execute_query(
        "MATCH (d:Drug {kr_market: false}) RETURN count(d) AS c", database_="neo4j"
    )[0][0]["c"]
    driver.execute_query(
        "MATCH (d:Drug {kr_market: false}) DETACH DELETE d", database_="neo4j"
    )
    print(f"[apply] non-kr Drug {n:,}개 + 딸린 관계 삭제 완료")
    return n


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--apply"]
    do_apply = "--apply" in sys.argv[1:]
    hira = Path(args[0]) if args else HIRA_ATC_CSV
    kr_atc = load_kr_atc(hira)

    driver = get_driver()
    try:
        driver.verify_connectivity()
        classify_and_tag(driver, kr_atc)
        if do_apply:
            apply_delete(driver)
            print("[done] 한국 필터 적용 완료")
        else:
            print("[done] 리뷰 모드 — 삭제 안 함. 후보 확인 후 --apply 로 실제 삭제.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
