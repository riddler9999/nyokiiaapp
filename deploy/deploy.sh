#!/bin/bash
# Generic auto-deploy script for any Docker Compose project.
# Called by webhook.py with project-specific arguments.
#
# Usage: deploy.sh <app_dir> [branch] [compose_file]

set -e

APP_DIR="${1:?Usage: deploy.sh <app_dir> [branch] [compose_file]}"
BRANCH="${2:-main}"
COMPOSE_FILE="${3:-docker-compose.yml}"
LOG_FILE="/var/log/autodeploy.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$APP_DIR] $1" | tee -a "$LOG_FILE"
}

log "=== Deploy started ==="

cd "$APP_DIR"

# Pull latest code
log "Pulling latest code from $BRANCH..."
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

# Rebuild and restart containers
log "Rebuilding Docker containers..."
docker compose -f "$COMPOSE_FILE" down
docker compose -f "$COMPOSE_FILE" up -d --build

log "Waiting for container to start..."
sleep 5

# Check if container is running
if docker compose -f "$COMPOSE_FILE" ps | grep -q "running"; then
    log "Deploy successful! Container is running."
else
    log "ERROR: Container failed to start!"
    docker compose -f "$COMPOSE_FILE" logs --tail=20 >> "$LOG_FILE" 2>&1
    exit 1
fi

log "=== Deploy completed ==="
