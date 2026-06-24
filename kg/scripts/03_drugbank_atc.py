"""Step 4: DrugBank ID ↔ ATC 코드 매핑 테이블을 생성한다.

중요: DrugBank open `vocabulary.csv`에는 ATC 코드가 없다. ATC는 학술 라이선스로 받는
full DrugBank XML(`full database.xml`)의 <atc-codes>에만 존재한다.

입력(확장자로 모드 자동 판별):
  - .xml : full DrugBank XML 스트리밍 파싱 (메인 경로)
  - .csv : 이미 drugbank_id/atc 컬럼이 있는 사전 매핑 CSV 정규화 (폴백)

출력: kg/data/drugbank_atc.csv  (컬럼: drugbank_id, name, atc_code)
      약물 1개가 ATC 여러 개를 가지면 행을 분리한다.

사용:
    python kg/scripts/03_drugbank_atc.py <full_database.xml | mapping.csv> [출력.csv]
"""

from __future__ import annotations

import csv
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from _common import DRUGBANK_ATC_CSV

NS = "{http://www.drugbank.ca}"


def parse_xml(path: str, dst: Path) -> None:
    """full DrugBank XML을 스트리밍 파싱해 drugbank_id↔atc를 추출한다."""
    drugs_total = 0
    drugs_with_atc = 0
    rows_written = 0

    with open(dst, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["drugbank_id", "name", "atc_code"])

        # 최상위 <drug> 만 처리 (salts 등 중첩 drug 요소 제외 위해 depth 추적)
        depth = 0
        for event, elem in ET.iterparse(path, events=("start", "end")):
            if event == "start" and elem.tag == NS + "drug":
                depth += 1
                continue
            if event != "end" or elem.tag != NS + "drug":
                continue

            depth -= 1
            if depth != 0:  # 중첩된 drug 요소는 무시
                elem.clear()
                continue

            primary = elem.find(NS + "drugbank-id[@primary='true']")
            db_id = primary.text if primary is not None else None
            name = elem.findtext(NS + "name")
            atc_codes = [
                ac.get("code")
                for ac in elem.findall(NS + "atc-codes/" + NS + "atc-code")
                if ac.get("code")
            ]

            drugs_total += 1
            if atc_codes and db_id:
                drugs_with_atc += 1
                for code in atc_codes:
                    writer.writerow([db_id, name, code])
                    rows_written += 1

            elem.clear()  # 메모리 해제

    print(f"[xml] 약물 총 {drugs_total:,}개 / ATC 보유 {drugs_with_atc:,}개")
    print(f"[saved] {dst} ({rows_written:,} rows)")


def normalize_csv(path: str, dst: Path) -> None:
    """이미 ATC가 든 CSV를 표준 컬럼으로 정규화한다."""
    df = pd.read_csv(path, dtype=str)
    cols = {c.lower().strip(): c for c in df.columns}

    def pick(*cands: str) -> str | None:
        for c in cands:
            if c in cols:
                return cols[c]
        return None

    id_col = pick("drugbank_id", "drugbank id", "drugbank-id")
    atc_col = pick("atc_code", "atc", "atc code", "atc-code")
    name_col = pick("name", "common name", "drug")
    if not id_col or not atc_col:
        raise SystemExit(
            f"CSV에서 drugbank_id/atc 컬럼을 찾지 못함. 실제 컬럼: {list(df.columns)}"
        )

    out = df[[id_col, name_col, atc_col]].copy() if name_col else df[[id_col, atc_col]].copy()
    out.columns = ["drugbank_id", "name", "atc_code"] if name_col else ["drugbank_id", "atc_code"]
    if "name" not in out.columns:
        out["name"] = ""
    out = out[["drugbank_id", "name", "atc_code"]].dropna(subset=["drugbank_id", "atc_code"])
    out = out.drop_duplicates()
    out.to_csv(dst, index=False)
    print(f"[csv] 정규화 완료")
    print(f"[saved] {dst} ({len(out):,} rows)")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = sys.argv[1]
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else DRUGBANK_ATC_CSV
    print(f"[load] {src}")
    if src.lower().endswith(".xml"):
        parse_xml(src, dst)
    else:
        normalize_csv(src, dst)


if __name__ == "__main__":
    main()
