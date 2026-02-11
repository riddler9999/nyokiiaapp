#!/bin/bash
# Auto-deploy script for Dhamma Audio-to-Video app
# Called by webhook listener when GitHub push event is received

set -e

APP_DIR="/root/nyokiiaapp"
LOG_FILE="/var/log/dhamma-deploy.log"
BRANCH="main"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Deploy started ==="

cd "$APP_DIR"

# Pull latest code
log "Pulling latest code from $BRANCH..."
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

# Rebuild and restart containers
log "Rebuilding Docker containers..."
docker compose down
docker compose up -d --build

log "Waiting for container to start..."
sleep 5

# Check if container is running
if docker compose ps | grep -q "running"; then
    log "Deploy successful! Container is running."
else
    log "ERROR: Container failed to start!"
    docker compose logs --tail=20 dhamma-converter >> "$LOG_FILE" 2>&1
    exit 1
fi

log "=== Deploy completed ==="
