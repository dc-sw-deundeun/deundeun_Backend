// 외부 의학 KG 스키마 — 제약(=인덱스) 및 보조 인덱스
// MERGE 성능과 노드 중복 방지를 위해 적재(05_load_neo4j.py) 전에 먼저 적용한다.

CREATE CONSTRAINT disease_mondo_id IF NOT EXISTS
FOR (d:Disease) REQUIRE d.mondo_id IS UNIQUE;

CREATE CONSTRAINT drug_drugbank_id IF NOT EXISTS
FOR (d:Drug) REQUIRE d.drugbank_id IS UNIQUE;

CREATE CONSTRAINT effect_hpo_id IF NOT EXISTS
FOR (e:Effect) REQUIRE e.hpo_id IS UNIQUE;

// 조회용 보조 인덱스 — ATC 기준 조인(DUR 단계)에 사용. 대표 ATC(atc_code) 단일값 인덱스.
CREATE INDEX drug_atc_code IF NOT EXISTS
FOR (d:Drug) ON (d.atc_code);
