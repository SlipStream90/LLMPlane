#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# LLMPlane — Manual Deploy Script
# ──────────────────────────────────────────────────────────────
# For manual deploys or servers without GitHub Actions SSH access.
#
# Usage:
#   ./deploy.sh                    # Deploy latest from registry
#   ./deploy.sh v0.1.0-alpha       # Deploy specific version tag
#   ./deploy.sh --local            # Build and deploy from local source
#
# Env vars:
#   DEPLOY_HOST      — SSH host (or run on the target server directly)
#   DEPLOY_USER      — SSH user
#   DEPLOY_PATH      — Project path on server (default: /opt/llmplane)
#   REGISTRY         — Container registry (default: ghcr.io)
#   IMAGE_PREFIX     — Image prefix (default: your-org/llmplane)
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_PREFIX="${IMAGE_PREFIX:-}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/llmplane}"
VERSION="${1:-latest}"
LOCAL_BUILD=false

if [ "$VERSION" = "--local" ]; then
    LOCAL_BUILD=true
    VERSION="local"
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $*"; }
err()  { echo -e "${RED}[deploy]${NC} $*" >&2; }

# ── Local build path ──────────────────────────────────────────
if [ "$LOCAL_BUILD" = true ]; then
    log "Building images locally ..."
    cd "$PROJECT_ROOT/docker"

    docker compose build backend frontend workers

    log "Restarting services ..."
    docker compose up -d --force-recreate backend workers frontend

    log "Pruning old images ..."
    docker image prune -f --filter "until=168h"

    log "Deploy complete (local build)"
    docker compose ps
    exit 0
fi

# ── Remote deploy path ────────────────────────────────────────
if [ -z "$IMAGE_PREFIX" ]; then
    err "IMAGE_PREFIX not set. Example: ghcr.io/your-org/llmplane"
    exit 1
fi

BACKEND_IMAGE="${REGISTRY}/${IMAGE_PREFIX}/backend:${VERSION}"
FRONTEND_IMAGE="${REGISTRY}/${IMAGE_PREFIX}/frontend:${VERSION}"
WORKERS_IMAGE="${REGISTRY}/${IMAGE_PREFIX}/workers:${VERSION}"

log "Deploying version: $VERSION"
log "  Backend:  $BACKEND_IMAGE"
log "  Frontend: $FRONTEND_IMAGE"
log "  Workers:  $WORKERS_IMAGE"

# Create deploy override compose file
TEMPCompose=$(mktemp)
cat > "$TEMPCompose" <<EOF
services:
  backend:
    image: ${BACKEND_IMAGE}
  frontend:
    image: ${FRONTEND_IMAGE}
  workers:
    image: ${WORKERS_IMAGE}
EOF

log "Pulling images ..."
docker compose -f docker-compose.yml -f "$TEMPCompose" pull

log "Restarting backend ..."
docker compose -f docker-compose.yml -f "$TEMPCompose" up -d --no-deps backend
sleep 10

log "Restarting workers ..."
docker compose -f docker-compose.yml -f "$TEMPCompose" up -d --no-deps workers
sleep 5

log "Restarting frontend ..."
docker compose -f docker-compose.yml -f "$TEMPCompose" up -d --no-deps frontend

rm -f "$TEMPCompose"

log "Pruning old images ..."
docker image prune -f --filter "until=168h"

log "Deploy complete!"
docker compose ps
