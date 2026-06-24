"""Step 5: 심평원(HIRA) 의약품 ATC 매핑을 표준 컬럼으로 정규화한다.

공공데이터포털에서 받은 심평원 ATC 매핑 파일(품목기준코드↔주성분코드↔ATC)을 입력받아
정규화한다. 심평원 파일은 배포 시점마다 컬럼명이 다르므로 후보 컬럼명으로 자동 매핑하며,
못 찾으면 실제 컬럼 목록을 출력하니 COLUMN_CANDIDATES를 보정한다.

입력: .csv 또는 .xlsx (openpyxl 필요)
출력: kg/data/hira_atc.csv
      컬럼: item_seq(품목기준코드), main_ingr_code(주성분코드), atc_code, atc_name, product_name

사용:
    python kg/scripts/04_hira_atc.py <hira_atc.csv|.xlsx> [출력.csv]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from _common import HIRA_ATC_CSV

# 출력 필드 -> 입력 후보 컬럼명(부분일치, 한글/영문 변형 대응)
COLUMN_CANDIDATES: dict[str, list[str]] = {
    "item_seq": ["품목기준코드", "품목일련번호", "제품코드", "item_seq", "품목코드"],
    "main_ingr_code": ["주성분코드", "성분코드", "main_ingr", "주성분일련번호"],
    "atc_code": ["atc코드", "atc 코드", "atc_code", "atc"],
    "atc_name": ["atc코드명", "atc명", "atc_name", "성분명(atc)"],
    "product_name": ["제품명", "품목명", "product_name", "의약품명"],
}


def read_any(path: str) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path, dtype=str)
    # 한글 CSV는 cp949/euc-kr 인 경우가 많아 utf-8 실패 시 재시도
    try:
        return pd.read_csv(path, dtype=str)
    except UnicodeDecodeError:
        return pd.read_csv(path, dtype=str, encoding="cp949")


def match_column(df_cols: list[str], candidates: list[str]) -> str | None:
    norm = {c: c.lower().replace(" ", "") for c in df_cols}
    for cand in candidates:
        key = cand.lower().replace(" ", "")
        for original, n in norm.items():
            if key in n:
                return original
    return None


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = sys.argv[1]
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else HIRA_ATC_CSV

    print(f"[load] {src}")
    df = read_any(src)
    df_cols = list(df.columns)

    resolved: dict[str, str] = {}
    missing: list[str] = []
    for out_field, cands in COLUMN_CANDIDATES.items():
        col = match_column(df_cols, cands)
        if col:
            resolved[out_field] = col
        else:
            missing.append(out_field)

    print(f"[map] 매핑된 컬럼: {resolved}")
    if "atc_code" not in resolved or "item_seq" not in resolved:
        raise SystemExit(
            f"필수 컬럼(item_seq/atc_code) 매핑 실패. 실제 컬럼: {df_cols}\n"
            "COLUMN_CANDIDATES를 실제 헤더에 맞게 보정하세요."
        )
    if missing:
        print(f"[warn] 미발견 컬럼(공백 처리): {missing}")

    out = pd.DataFrame()
    for out_field in COLUMN_CANDIDATES:
        out[out_field] = df[resolved[out_field]] if out_field in resolved else ""

    out = out.dropna(subset=["item_seq", "atc_code"]).drop_duplicates()
    out.to_csv(dst, index=False)
    print(f"[saved] {dst} ({len(out):,} rows)")


if __name__ == "__main__":
    main()
