#!/usr/bin/env bash
# 외부 의학 KG Neo4j 엔트리포인트.
# /dumps/neo4j.dump 가 있고 아직 로드 전(/data/.kg_loaded 없음)이면 최초 1회 자동 로드 후 서버를 기동한다.
# read-only KG라 첫 기동에만 로드하고 이후엔 스킵한다.
set -euo pipefail

DUMP=/dumps/neo4j.dump
MARKER=/data/.kg_loaded

# neo4j 서버 기동이 아닌 다른 명령(예: neo4j-admin)은 공식 엔트리포인트에 그대로 위임
if [ "$#" -gt 0 ] && [ "$1" != "neo4j" ]; then
  exec /startup/docker-entrypoint.sh "$@"
fi

if [ -f "$DUMP" ] && [ ! -f "$MARKER" ]; then
  echo "[entrypoint] dump 발견 → 최초 1회 로드: $DUMP"
  chown -R neo4j:neo4j /data 2>/dev/null || true
  su neo4j -s /bin/bash -c \
    "neo4j-admin database load neo4j --from-path=/dumps --overwrite-destination=true"
  touch "$MARKER"
  echo "[entrypoint] dump 로드 완료"
else
  echo "[entrypoint] dump 미발견 또는 이미 로드됨 → 그대로 기동"
fi

# 공식 엔트리포인트로 위임 (root로 실행되어 권한 정리 후 neo4j 유저로 강등·기동)
exec /startup/docker-entrypoint.sh neo4j
