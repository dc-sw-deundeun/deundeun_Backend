"""외부 의학 KG(PrimeKG kg.csv) → 조건별 의학 이웃 시드 오프라인 추출.

app/domains/pkg/data/condition_mondo_map.json(조건→MONDO 노드 id)을 기준으로, kg.csv를
스트리밍 파싱(csv 모듈, 982MB 메모리안전)해 조건별 disease_disease(합병증)·
disease_phenotype_positive(증상)·exposure_disease(노출인자) 이웃을 추출한다. 결과는
app/domains/pkg/data/condition_neighborhood.json으로 저장 — 런타임/CI는 이 시드만 쓰고
원본 kg.csv에 의존하지 않는다.

추출 로직은 app.domains.pkg.neighborhood.extract_neighborhood(순수·테스트됨)에 있고, 이
스크립트는 파일 I/O만 담당한다.

사용:
    python scripts/extract_condition_neighborhood.py \
        --kg kg/data/kg.csv \
        --mondo-map app/domains/pkg/data/condition_mondo_map.json \
        --out app/domains/pkg/data/condition_neighborhood.json
"""

import argparse
import csv
import json
import sys
from collections.abc import Iterator
from pathlib import Path

# 앱 모듈 import를 위해 저장소 루트를 경로에 추가.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domains.pkg.neighborhood import KgRow, extract_neighborhood  # noqa: E402

# kg.csv 헤더: relation,display_relation,x_index,x_id,x_type,x_name,x_source,
#              y_index,y_id,y_type,y_name,y_source
_X_ID, _X_TYPE, _X_NAME = 3, 4, 5
_Y_ID, _Y_TYPE, _Y_NAME = 8, 9, 10
_MIN_COLS = 11


def _iter_kg_rows(kg_path: Path) -> Iterator[KgRow]:
    with kg_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # 헤더 스킵
        for row in reader:
            if len(row) <= _Y_NAME:
                continue
            yield (
                row[0],
                row[_X_ID],
                row[_X_TYPE],
                row[_X_NAME],
                row[_Y_ID],
                row[_Y_TYPE],
                row[_Y_NAME],
            )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kg", type=Path, default=root / "kg/data/kg.csv")
    parser.add_argument(
        "--mondo-map",
        type=Path,
        default=root / "app/domains/pkg/data/condition_mondo_map.json",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=root / "app/domains/pkg/data/condition_neighborhood.json",
    )
    parser.add_argument("--cap", type=int, default=25, help="조건·버킷당 최대 항목 수")
    args = parser.parse_args()

    mondo_map = json.loads(args.mondo_map.read_text(encoding="utf-8"))["map"]
    conditions = extract_neighborhood(_iter_kg_rows(args.kg), mondo_map, cap=args.cap)

    payload = {
        "_doc": (
            "조건 id → 외부 의학 KG(PrimeKG) 이웃 사실. "
            "complications=disease_disease, phenotypes=disease_phenotype_positive, "
            "exposures=exposure_disease. scripts/extract_condition_neighborhood.py가 "
            "kg/data/kg.csv에서 오프라인 생성(재현 가능). 이름은 PrimeKG 원문(영어) 그대로 — "
            "생활미션으로의 번역은 생성 LLM 몫. exposures는 환경 독성물질도 섞여 있어 "
            "소비 단계(P2/P3)에서 가중치·필터 필요."
        ),
        "conditions": conditions,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total = sum(len(v) for c in conditions.values() for v in c.values())
    print(f"wrote {args.out} — {len(conditions)} conditions, {total} facts")


if __name__ == "__main__":
    main()
