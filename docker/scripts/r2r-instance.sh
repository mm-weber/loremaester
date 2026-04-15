#!/bin/bash
# Manage an R2R application instance.
#
# Usage:
#   r2r-instance.sh <instance> up        — start instance
#   r2r-instance.sh <instance> down      — stop instance
#   r2r-instance.sh <instance> status    — show service status
#   r2r-instance.sh <instance> logs      — tail logs
#   r2r-instance.sh <instance> restart   — restart all (or specific) services
#
# Examples:
#   r2r-instance.sh ttrpg up
#   r2r-instance.sh coding up
#   r2r-instance.sh ttrpg restart r2r
#   r2r-instance.sh ttrpg logs r2r

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOCKER_DIR="$(dirname "$SCRIPT_DIR")/docker"

if [ ! -f "$DOCKER_DIR/compose.app.yaml" ]; then
  DOCKER_DIR="$SCRIPT_DIR"
fi

INSTANCE="${1:?Usage: r2r-instance.sh <instance> <action> [args...]}"
shift
ACTION="${1:-status}"
shift 2>/dev/null || true

ENV_FILE="$DOCKER_DIR/instances/$INSTANCE/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: instance '$INSTANCE' not found (no $ENV_FILE)" >&2
  echo "Available instances:" >&2
  ls -1 "$DOCKER_DIR/instances/" 2>/dev/null || echo "  (none)" >&2
  exit 1
fi

# Check that infra network exists
if ! docker network inspect r2r-infra >/dev/null 2>&1; then
  echo "Warning: r2r-infra network not found. Start infrastructure first:" >&2
  echo "  r2r-infra.sh up" >&2
  if [ "$ACTION" = "up" ]; then
    exit 1
  fi
fi

case "$ACTION" in
  up)
    docker compose -f "$DOCKER_DIR/compose.app.yaml" --env-file "$ENV_FILE" up -d "$@"
    echo "Instance '$INSTANCE' started."
    docker compose -f "$DOCKER_DIR/compose.app.yaml" --env-file "$ENV_FILE" \
      ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    ;;
  down)
    docker compose -f "$DOCKER_DIR/compose.app.yaml" --env-file "$ENV_FILE" down "$@"
    ;;
  status|ps)
    docker compose -f "$DOCKER_DIR/compose.app.yaml" --env-file "$ENV_FILE" \
      ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
    ;;
  logs)
    docker compose -f "$DOCKER_DIR/compose.app.yaml" --env-file "$ENV_FILE" logs -f "$@"
    ;;
  restart)
    docker compose -f "$DOCKER_DIR/compose.app.yaml" --env-file "$ENV_FILE" restart "$@"
    ;;
  *)
    docker compose -f "$DOCKER_DIR/compose.app.yaml" --env-file "$ENV_FILE" "$ACTION" "$@"
    ;;
esac
