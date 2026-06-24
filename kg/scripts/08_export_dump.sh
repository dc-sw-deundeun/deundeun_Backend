#!/usr/bin/env bash
# Step 8: 적재 완료된 Neo4j DB를 dump로 추출한다 (배포 이미지 자동 로드용).
# dump/load는 DB 오프라인 상태에서만 가능하므로 정지 후 추출한다.
# 결과: kg/data/dumps/neo4j.dump  (Google Drive 업로드, Git 제외)
#
# 사용: bash kg/scripts/08_export_dump.sh
set -euo pipefail

COMPOSE="docker compose -f docker/docker-compose.yml"
DUMP_DIR="kg/data/dumps"
mkdir -p "$DUMP_DIR"

echo "[export] neo4j 정지"
$COMPOSE stop neo4j

echo "[export] dump 생성 → $DUMP_DIR/neo4j.dump"
$COMPOSE run --rm --no-deps --entrypoint neo4j-admin \
  -v "$(pwd)/$DUMP_DIR:/export" neo4j \
  database dump neo4j --to-path=/export --overwrite-destination=true

echo "[export] neo4j 재기동"
$COMPOSE start neo4j

echo "[done] $DUMP_DIR/neo4j.dump — Google Drive에 업로드하세요 (Git 제외)"
