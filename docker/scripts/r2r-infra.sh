#!/bin/bash
# Manage shared R2R infrastructure (postgres, hatchet, minio).
#
# Usage:
#   r2r-infra.sh up       — start infra (postgres + minio profiles enabled)
#   r2r-infra.sh down     — stop infra
#   r2r-infra.sh status   — show service status
#   r2r-infra.sh logs     — tail logs
#
# Any extra arguments are passed through to docker compose.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")/docker"

if [ ! -f "$DOCKER_DIR/compose.infra.yaml" ]; then
  DOCKER_DIR="$SCRIPT_DIR"
fi

ACTION="${1:-status}"
shift 2>/dev/null || true

case "$ACTION" in
  up)
    docker compose -f "$DOCKER_DIR/compose.infra.yaml" -p r2r-infra \
      --profile postgres --profile minio up -d "$@"
    echo "Waiting for infrastructure to become healthy..."
    docker compose -f "$DOCKER_DIR/compose.infra.yaml" -p r2r-infra \
      ps --format "table {{.Name}}\t{{.Status}}"
    ;;
  down)
    docker compose -f "$DOCKER_DIR/compose.infra.yaml" -p r2r-infra down "$@"
    ;;
  status|ps)
    docker compose -f "$DOCKER_DIR/compose.infra.yaml" -p r2r-infra \
      ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    ;;
  logs)
    docker compose -f "$DOCKER_DIR/compose.infra.yaml" -p r2r-infra logs -f "$@"
    ;;
  *)
    docker compose -f "$DOCKER_DIR/compose.infra.yaml" -p r2r-infra "$ACTION" "$@"
    ;;
esac
