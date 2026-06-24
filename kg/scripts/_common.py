"""KG ETL 스크립트 공통 경로/설정/유틸.

모든 스크립트는 `python kg/scripts/NN_xxx.py` 형태로 실행한다 (스크립트 디렉토리가 sys.path에 추가됨).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# kg/scripts/_common.py -> 레포 루트는 두 단계 위
REPO_ROOT = Path(__file__).resolve().parents[2]
KG_DIR = REPO_ROOT / "kg"
DATA_DIR = KG_DIR / "data"
MAPPINGS_DIR = KG_DIR / "mappings"
DUMPS_DIR = DATA_DIR / "dumps"

# 데이터 산출물 (Git 제외)
KG_CSV = DATA_DIR / "kg.csv"
KG_CLINICAL_CSV = DATA_DIR / "kg_clinical.csv"
DRUGBANK_ATC_CSV = DATA_DIR / "drugbank_atc.csv"
HIRA_ATC_CSV = DATA_DIR / "hira_atc.csv"

# 커밋되는 매핑 산출물
MAPPING_TABLE = MAPPINGS_DIR / "mapping_table.json"

# .env 로드 (없어도 무시)
load_dotenv(REPO_ROOT / ".env")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "change-me")

# 식약처 DUR API (공공데이터포털 - 의약품 DUR정보)
DUR_API_KEY = os.getenv("DUR_API_KEY")
DUR_BASE_URL = os.getenv(
    "DUR_BASE_URL", "http://apis.data.go.kr/1471000/DURPrdlstInfoService03"
)


def get_driver():
    """Neo4j 드라이버를 반환한다. 호출 측에서 close() 책임.

    neo4j 패키지는 적재/검증 스크립트에서만 필요하므로 지연 import 한다.
    """
    from neo4j import GraphDatabase

    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
