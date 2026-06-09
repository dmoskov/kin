#!/usr/bin/env bash
# Nightly database backup: pg_dump → S3.
#
# Runs on the production server via systemd timer (familytree-backup.timer,
# installed by setup.sh). Run manually with:
#
#   bash /home/ec2-user/family-tree/deploy/backup.sh
#
# Configuration (read from the app's .env file):
#   DATABASE_URL           required — the database to back up
#   BACKUP_S3_BUCKET       S3 bucket for backups; falls back to S3_BUCKET
#   BACKUP_S3_PREFIX       key prefix (default: backups/db)
#   BACKUP_RETENTION_DAYS  delete backups older than this (default: 30)
#
# Restore instructions: see deploy/BACKUPS.md

set -euo pipefail

ENV_FILE="${ENV_FILE:-/home/ec2-user/family-tree/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: env file not found at $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "Error: DATABASE_URL is not set in $ENV_FILE — nothing to back up." >&2
  exit 1
fi

BUCKET="${BACKUP_S3_BUCKET:-${S3_BUCKET:-}}"
if [[ -z "$BUCKET" ]]; then
  echo "Error: set BACKUP_S3_BUCKET (or S3_BUCKET) in $ENV_FILE." >&2
  exit 1
fi

PREFIX="${BACKUP_S3_PREFIX:-backups/db}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

for cmd in pg_dump aws; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: $cmd not found. Run deploy/setup.sh to install prerequisites." >&2
    exit 1
  fi
done

STAMP="$(date -u +%Y-%m-%dT%H%M%SZ)"
KEY="$PREFIX/familytree-$STAMP.dump"
TMP="$(mktemp /tmp/familytree-backup.XXXXXX.dump)"
trap 'rm -f "$TMP"' EXIT

# ── Dump ──────────────────────────────────────────────────────────────────
# Custom format (-Fc): compressed, and pg_restore can do partial/reordered
# restores from it.
echo "Dumping database..."
pg_dump --format=custom --no-owner --no-privileges \
  --dbname="$DATABASE_URL" --file="$TMP"

SIZE=$(stat -c %s "$TMP" 2>/dev/null || stat -f %z "$TMP")
if [[ "$SIZE" -lt 10000 ]]; then
  echo "Error: dump is suspiciously small ($SIZE bytes) — refusing to upload." >&2
  exit 1
fi

# ── Upload + verify ───────────────────────────────────────────────────────
echo "Uploading to s3://$BUCKET/$KEY ($SIZE bytes)..."
aws s3 cp --only-show-errors "$TMP" "s3://$BUCKET/$KEY"
aws s3api head-object --bucket "$BUCKET" --key "$KEY" >/dev/null

# ── Prune backups older than RETENTION_DAYS ───────────────────────────────
CUTOFF="$(date -u -d "-$RETENTION_DAYS days" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
       || date -u -v "-${RETENTION_DAYS}d" +%Y-%m-%dT%H:%M:%SZ)"
echo "Pruning backups older than $CUTOFF..."
aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "$PREFIX/" \
  --query "Contents[?LastModified<'$CUTOFF'].Key" --output text \
  | tr '\t' '\n' | grep -v '^None$' | grep . \
  | while read -r old_key; do
      echo "  deleting s3://$BUCKET/$old_key"
      aws s3 rm --only-show-errors "s3://$BUCKET/$old_key"
    done || true

echo "Backup complete: s3://$BUCKET/$KEY"
