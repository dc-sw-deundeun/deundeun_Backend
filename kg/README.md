# 외부 의학 KG (Medical Knowledge Graph)

신규 검진 이벤트(연 1회) 시 PKG와 조인되는 **read-only 외부 의학 지식 소스**.
PrimeKG(질병–약물–효과) + 한국 검진 finding↔MONDO 조인 키 + 식약처 DUR 안전 레이어를
Neo4j(Community 5.26)에 적재하고, 최종적으로 **Docker 이미지(dump 최초 1회 자동 로드)** 로 패키징한다.

> KG는 한 번 만들면 바뀌지 않는다(read-only). **사용자 데이터는 절대 기록하지 않는다.**

## 산출물 분리

| 분류 | 대상 | 위치 |
|------|------|------|
| Git 커밋 | 스크립트, Dockerfile, compose, cypher, `mappings/mapping_table.json` | 레포 |
| Google Drive (Git 제외) | `medical_kg.dump`, 원본 `kg.csv`, 중간 CSV | `kg/data/` (gitignore) |
| 로컬 전용 | Neo4j data | docker named volume |

## 사전 준비

```bash
# ETL 전용 가상환경
python -m venv kg/.venv-kg
source kg/.venv-kg/bin/activate
pip install -r kg/requirements-kg.txt

# 환경변수 (.env — NEO4J_* 채우기, .env.example 참고)
cp .env.example .env   # 이미 있으면 NEO4J_* 항목만 추가
```

필요한 외부 데이터/키:
- `kg.csv` — PrimeKG (Harvard Dataverse, DOI 10.7910/DVN/IXA7BM)
- DrugBank open data `vocabulary.csv` (계정 필요)
- 공공데이터포털 — 심평원 의약품 ATC 매핑
- 식약처 DUR API 키

## 실행 순서

| Step | 명령 | 산출물 |
|------|------|--------|
| 1 | `kg.csv`를 `kg/data/`에 다운로드 | `kg/data/kg.csv` |
| 2 | `python kg/scripts/01_inspect_diseases.py` | MONDO 후보 → `kg/mappings/mapping_table.json` 수동 확정 |
| 3 | `python kg/scripts/02_filter_primekg.py` | `kg/data/kg_clinical.csv` + 카운트 리포트 |
| 4 | `python kg/scripts/03_drugbank_atc.py` | `kg/data/drugbank_atc.csv` |
| 5 | `python kg/scripts/04_hira_atc.py` | `kg/data/hira_atc.csv` |
| 6 | `docker compose -f docker/docker-compose.yml up -d neo4j` → `python kg/scripts/05_load_neo4j.py` | Neo4j 적재 |
| 7 | `python kg/scripts/06_dur_enrichment.py` / `07_food_interaction.py` | DUR 금기·약물식품 엣지 |
| 8 | `bash kg/scripts/08_export_dump.sh` | `kg/data/dumps/neo4j.dump` |
| 9 | `python kg/scripts/09_verify.py` (또는 `cypher/verify.cypher`) | 검증 카운트/멀티홉 |

## 배포 (Docker 패키징)

`docker/neo4j` 커스텀 이미지는 `/dumps/neo4j.dump`가 있으면 **최초 1회 자동 로드** 후 기동한다.

```bash
# 1) Google Drive에서 받은 dump를 배치
cp <다운로드>/neo4j.dump kg/data/dumps/neo4j.dump
# 2) 기동 (최초 1회 자동 로드, 이후 재기동 시 스킵)
docker compose -f docker/docker-compose.yml up -d --build neo4j
```

- 개발/적재 시엔 dump 없이 빈 DB로 떠서 `05_load_neo4j.py`로 적재한다(같은 서비스).
- dump를 다시 로드하려면 `neo4j_data` 볼륨 또는 `/data/.kg_loaded` 마커를 제거한다.

## 그래프 스키마

```
(:Disease {mondo_id, name, source})
(:Drug    {drugbank_id, name, atc_code, source, age_contraindication?, pregnancy_contraindication?})
(:Effect  {hpo_id, name, source})
(:Food    {name})                                  # DUR/DDID 단계에서 생성

(x)-[:RELATION {type, source}]->(y)                # PrimeKG 관계 (type=display_relation)
(:Drug)-[:CONTRAINDICATED_WITH {source}]->(:Drug)  # DUR 병용금기
(:Drug)-[:FOOD_INTERACTION {effect, severity}]->(:Food)
```

인덱스/제약: `Disease(mondo_id)` UNIQUE, `Drug(drugbank_id)` UNIQUE, `Effect(hpo_id)` UNIQUE, `Drug(atc_code)` INDEX

## 제약
- 외부 KG는 **read-only** — 사용자 데이터 기록 금지
- MONDO ID는 Step 2에서 직접 조회·확정한 값만 사용 (추정값 금지)
- 분자 레이어 prune 후 disease–disease 직접 연결이 끊길 수 있음 → COMORBID_WITH는 별도 이슈(브리지 레이어)
