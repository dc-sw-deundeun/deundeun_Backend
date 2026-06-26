#!/usr/bin/env bash
# SSH 대상 서버 배포 스크립트
# 사용법: bash deploy.sh <IMAGE_TAG>
# 예시:   bash deploy.sh deundeun/backend:sha-abc1234

set -euo pipefail

IMAGE_TAG="${1:?IMAGE_TAG argument is required}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/deundeun}"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
APP_ENV_FILE="${APP_ENV_FILE:-$DEPLOY_DIR/.env}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "[deploy] Compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

if [[ ! -f "$APP_ENV_FILE" ]]; then
  echo "[deploy] App env file not found: $APP_ENV_FILE" >&2
  exit 1
fi

read_env_value() {
  local key="$1"
  local default_value="$2"
  local value

  value="$(grep -E "^${key}=" "$APP_ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"

  if [[ -n "$value" ]]; then
    printf '%s' "$value"
  else
    printf '%s' "$default_value"
  fi
}

API_SERVICE="${API_SERVICE:-$(read_env_value API_SERVICE api)}"
API_CONTAINER_NAME="${API_CONTAINER_NAME:-$(read_env_value API_CONTAINER_NAME deundeun-api)}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-$(read_env_value RUN_MIGRATIONS true)}"
HEALTHCHECK_TIMEOUT_SECONDS="${HEALTHCHECK_TIMEOUT_SECONDS:-$(read_env_value HEALTHCHECK_TIMEOUT_SECONDS 60)}"
HEALTHCHECK_INTERVAL_SECONDS="${HEALTHCHECK_INTERVAL_SECONDS:-$(read_env_value HEALTHCHECK_INTERVAL_SECONDS 2)}"

export IMAGE_TAG
export APP_ENV_FILE
export API_CONTAINER_NAME

compose_cmd=(
  docker compose
  --env-file "$APP_ENV_FILE"
  -f "$COMPOSE_FILE"
  --profile deploy
)

wait_for_health() {
  local deadline status
  deadline=$((SECONDS + HEALTHCHECK_TIMEOUT_SECONDS))

  while ((SECONDS < deadline)); do
    status="$(
      docker inspect \
        --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{if .State.Running}}running{{else}}stopped{{end}}{{end}}' \
        "$API_CONTAINER_NAME" 2>/dev/null || true
    )"

    case "$status" in
      healthy | running)
        echo "[deploy] Container is $status"
        return 0
        ;;
      unhealthy | stopped)
        echo "[deploy] Container is $status"
        return 1
        ;;
      *)
        sleep "$HEALTHCHECK_INTERVAL_SECONDS"
        ;;
    esac
  done

  echo "[deploy] Healthcheck timed out after ${HEALTHCHECK_TIMEOUT_SECONDS}s" >&2
  return 1
}

echo "[deploy] Pulling image: $IMAGE_TAG"
docker pull "$IMAGE_TAG"

previous_image="$(
  docker inspect --format '{{.Config.Image}}' "$API_CONTAINER_NAME" 2>/dev/null || true
)"

if [[ "$RUN_MIGRATIONS" == "true" ]]; then
  echo "[deploy] Running migrations"
  "${compose_cmd[@]}" run --rm --no-deps "$API_SERVICE" alembic upgrade head
fi

echo "[deploy] Starting service with Compose"
"${compose_cmd[@]}" up -d --no-deps "$API_SERVICE"

if ! wait_for_health; then
  echo "[deploy] New container failed healthcheck" >&2
  "${compose_cmd[@]}" logs --tail=80 "$API_SERVICE" >&2 || true

  if [[ -n "$previous_image" && "$previous_image" != "$IMAGE_TAG" ]]; then
    echo "[deploy] Rolling back to previous image: $previous_image" >&2
    export IMAGE_TAG="$previous_image"
    "${compose_cmd[@]}" up -d --no-deps "$API_SERVICE"
    wait_for_health || true
  fi

  exit 1
fi

echo "[deploy] Done - $API_CONTAINER_NAME is running: $IMAGE_TAG"
