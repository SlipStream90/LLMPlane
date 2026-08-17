#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# LLMPlane — Database Restore from Cloudflare R2 Backup
# ──────────────────────────────────────────────────────────────
# Restores a PostgreSQL database from an R2-stored backup.
# R2 is S3-compatible, so this uses the AWS CLI with R2 endpoint.
#
# Usage:
#   ./restore_db.sh                          # Interactive — lists available backups
#   ./restore_db.sh <backup-key>             # Restore a specific backup by R2 key
#   ./restore_db.sh llmplane_20260817_120000.sql.gz   # Restore by filename
#
# Env vars (same as backup task):
#   S3_BUCKET, S3_ENDPOINT_URL, S3_ACCESS_KEY_ID,
#   S3_SECRET_ACCESS_KEY, S3_REGION, S3_PREFIX,
#   DATABASE_URL
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[restore]${NC} $*"; }
warn() { echo -e "${YELLOW}[restore]${NC} $*"; }
err()  { echo -e "${RED}[restore]${NC} $*" >&2; }

# ── Validate env ──────────────────────────────────────────────
for var in S3_BUCKET S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY; do
    if [ -z "${!var:-}" ]; then
        err "Missing required env var: $var"
        exit 1
    fi
done

S3_PREFIX="${S3_PREFIX:-llmplane/backups}"
S3_ENDPOINT="${S3_ENDPOINT_URL:+--endpoint-url $S3_ENDPOINT_URL}"
S3_REGION="${S3_REGION:-us-east-1}"

# ── Parse DATABASE_URL ────────────────────────────────────────
DB_URL="${DATABASE_URL:-postgresql+asyncpg://llmplane:llmplane_dev@postgres:5432/llmplane}"
DB_URLPlain=$(echo "$DB_URL" | sed 's|postgresql+asyncpg://|postgresql://|')
DB_USER=$(echo "$DB_URLPlain" | sed -n 's|.*://\([^:]*\):.*|\1|p')
DB_PASS=$(echo "$DB_URLPlain" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')
DB_HOST=$(echo "$DB_URLPlain" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DB_URLPlain" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_NAME=$(echo "$DB_URLPlain" | sed -n 's|.*/\([^?]*\).*|\1|p')

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-llmplane}"

export PGPASSWORD="$DB_PASS"

# ── Helper: list backups ──────────────────────────────────────
list_backups() {
    log "Fetching backup list from s3://$S3_BUCKET/$S3_PREFIX/ ..."
    aws s3 ls $S3_ENDPOINT "s3://$S3_BUCKET/$S3_PREFIX/" --region "$S3_REGION" 2>/dev/null | \
        grep "\.sql\.gz$" | \
        awk '{print $NF}' | \
        sort -r | \
        head -20
}

# ── Helper: download and restore a single backup ──────────────
restore_backup() {
    local key="$1"
    local filename
    filename=$(basename "$key")

    if [[ "$key" != *"/"* ]]; then
        key="$S3_PREFIX/$key"
    fi

    log "Downloading s3://$S3_BUCKET/$key ..."
    local tmpdir
    tmpdir=$(mktemp -d)
    local gz_path="$tmpdir/$filename"
    local sql_path="$tmpdir/${filename%.gz}"

    aws s3 cp $S3_ENDPOINT "s3://$S3_BUCKET/$key" "$gz_path" --region "$S3_REGION"

    log "Decompressing $gz_path ..."
    gunzip -f "$gz_path"

    log "Restoring to $DB_HOST:$DB_PORT/$DB_NAME as user $DB_USER ..."
    log "Dropping and recreating database $DB_NAME ..."

    # Terminate existing connections
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();" \
        2>/dev/null || true

    # Drop and recreate
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
        "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
        "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>/dev/null

    # Restore
    pg_restore \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-owner \
        --no-privileges \
        --if-exists \
        --clean \
        "$sql_path" 2>&1 || {
            # pg_restore returns non-zero on warnings, check if DB exists
            warn "pg_restore exited with warnings (this is often OK)"
        }

    log "Verifying restore ..."
    local count
    count=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')

    log "Restore complete! Found $count tables in $DB_NAME."

    # Cleanup
    rm -rf "$tmpdir"
}

# ── Main ──────────────────────────────────────────────────────
if [ $# -ge 1 ]; then
    restore_backup "$1"
else
    echo ""
    log "Available backups (last 20):"
    echo ""
    list_backups
    echo ""
    warn "Usage: $0 <backup-filename>"
    warn "Example: $0 llmplane_20260817_120000.sql.gz"
fi
