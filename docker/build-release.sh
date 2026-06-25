#!/usr/bin/env bash
# 배포용 self-contained Neo4j 이미지 빌드 (덤프 baked-in).
#
# 전제: kg/data/dumps/neo4j.dump 존재 (없으면 'bash kg/scripts/08_export_dump.sh' 먼저)
#
# 사용 예시:
#   # (1) 로컬 빌드만 (현재 호스트 아키텍처)
#   bash docker/build-release.sh v1
#
#   # (2) 로컬 빌드 + tar 추출 (파일 전송 핸드오프용)
#   SAVE=1 bash docker/build-release.sh v1
#
#   # (3) 레지스트리에 멀티아치로 push (Docker Hub 등) — 먼저 'docker login'
#   #     ⚠️ 반드시 PRIVATE 저장소로 (DrugBank 데이터는 공개 금지)
#   docker login
#   PUSH=1 IMAGE=<dockerhub-user>/medical-kg-neo4j:v1 \
#     PLATFORM=linux/amd64,linux/arm64 bash docker/build-release.sh v1
#
#   # (4) 단일 amd64(x86 VM용)만 로컬에 load
#   PLATFORM=linux/amd64 bash docker/build-release.sh v1
#
# 환경변수:
#   IMAGE     이미지 태그 (기본 deundeun/medical-kg-neo4j:$TAG)
#   PLATFORM  대상 플랫폼 (예: linux/amd64 / linux/amd64,linux/arm64). 미지정=호스트 아키텍처
#   PUSH=1    레지스트리 push (buildx --push). 멀티아치는 자동으로 push
#   SAVE=1    docker save → kg/data/dist/*.tar.gz (단일아치·로컬 load 시에만)
set -euo pipefail

TAG="${1:-v1}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DUMP="$REPO_ROOT/kg/data/dumps/neo4j.dump"
ENTRY="$REPO_ROOT/docker/neo4j/docker-entrypoint-kg.sh"
DOCKERFILE="$REPO_ROOT/docker/neo4j/Dockerfile.release"
IMAGE="${IMAGE:-deundeun/medical-kg-neo4j:$TAG}"
PLATFORM="${PLATFORM:-}"
PUSH="${PUSH:-0}"
SAVE="${SAVE:-0}"

[ -f "$DUMP" ] || { echo "[err] 덤프 없음: $DUMP — 먼저 'bash kg/scripts/08_export_dump.sh'"; exit 1; }

# 거대한 kg/data를 빌드 컨텍스트로 보내지 않도록 임시 디렉토리에 스테이징
CTX="$(mktemp -d)"
trap 'rm -rf "$CTX"' EXIT
cp "$ENTRY" "$CTX/docker-entrypoint-kg.sh"
cp "$DUMP" "$CTX/neo4j.dump"
cp "$DOCKERFILE" "$CTX/Dockerfile"

echo "[build] $IMAGE (덤프 baked-in, $(du -h "$DUMP" | cut -f1))"

if [ -n "$PLATFORM" ] || [ "$PUSH" = "1" ]; then
  # buildx 경로 (멀티아치/push)
  PLATFORM="${PLATFORM:-linux/amd64}"
  OUT="--load"
  case "$PLATFORM" in *,*) OUT="--push" ;; esac   # 멀티아치는 로컬 load 불가 → push 강제
  [ "$PUSH" = "1" ] && OUT="--push"
  echo "[buildx] platform=$PLATFORM output=$OUT"
  [ "$OUT" = "--push" ] && echo "[warn] PRIVATE 저장소인지 확인하세요 (DrugBank 데이터는 공개 금지)"
  docker buildx build --platform "$PLATFORM" -t "$IMAGE" $OUT "$CTX"
else
  docker build -t "$IMAGE" "$CTX"
fi
echo "[done] $IMAGE"

if [ "$SAVE" = "1" ]; then
  case "$PLATFORM" in *,*) echo "[skip] 멀티아치는 docker save 불가 (단일아치 로컬 load 시에만)"; exit 0 ;; esac
  [ "$PUSH" = "1" ] && { echo "[skip] PUSH 모드에선 로컬 이미지가 없어 save 생략"; exit 0; }
  DIST="$REPO_ROOT/kg/data/dist"; mkdir -p "$DIST"
  OUTF="$DIST/medical-kg-neo4j-$TAG.tar.gz"
  echo "[save] $OUTF 생성 중..."
  docker save "$IMAGE" | gzip > "$OUTF"
  echo "[done] 핸드오프 파일: $OUTF ($(du -h "$OUTF" | cut -f1))"
fi
