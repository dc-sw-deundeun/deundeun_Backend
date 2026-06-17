#!/usr/bin/env bash
# VM 배포 스크립트
# 사용법: bash deploy.sh <IMAGE_TAG>
# 예시:   bash deploy.sh deundeun/backend:sha-abc1234

set -euo pipefail

IMAGE_TAG="${1:?IMAGE_TAG argument is required}"
CONTAINER_NAME="deundeun-api"
ENV_FILE="/opt/deundeun/.env"
PORT="8000"

echo "[deploy] Pulling image: $IMAGE_TAG"
docker pull "$IMAGE_TAG"

echo "[deploy] Stopping existing container (if running)"
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm   "$CONTAINER_NAME" 2>/dev/null || true

echo "[deploy] Starting new container"
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "${PORT}:${PORT}" \
  --env-file "$ENV_FILE" \
  "$IMAGE_TAG"

echo "[deploy] Done — $CONTAINER_NAME is running"
