#!/usr/bin/env bash
# Dumps all 4 factorresearch databases and encrypts each backup file.
#
# Requires:
#   BACKUP_ENCRYPTION_KEY  — 32+ char passphrase (store in secrets manager, NOT in repo)
#   DATABASE_*_URL         — same env vars the app already uses
#
# Usage: ./scripts/backup_db.sh
# Intended to run via cron/systemd timer, e.g. nightly.

set -euo pipefail

# Load config from .env (repo root, or path given via ENV_FILE). Real secrets
# should still come from a secrets manager in prod — this just keeps local/
# staging runs consistent with how the app itself is configured (python-dotenv).
ENV_FILE="${ENV_FILE:-.env}"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
else
    echo "WARNING: $ENV_FILE not found — relying on already-exported environment variables." >&2
fi

BACKUP_DIR="${BACKUP_DIR:-/var/backups/factorresearch}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

if [ -z "${BACKUP_ENCRYPTION_KEY:-}" ]; then
    echo "ERROR: BACKUP_ENCRYPTION_KEY not set. Refusing to write unencrypted backups." >&2
    exit 1
fi

DBS=(
    "factorresearch_users:${DATABASE_USERS_URL:-}"
    "factorresearch_market:${DATABASE_MARKET_URL:-}"
    "factorresearch_analytics:${DATABASE_ANALYTICS_URL:-}"
)

for entry in "${DBS[@]}"; do
    name="${entry%%:*}"
    url="${entry#*:}"

    if [ -z "$url" ]; then
        echo "SKIP: no connection URL set for $name"
        continue
    fi

    raw_file="$BACKUP_DIR/${name}_${TIMESTAMP}.sql"
    enc_file="${raw_file}.enc"

    echo "Dumping $name..."
    pg_dump "$url" --format=custom --file="$raw_file"

    echo "Encrypting $name backup..."
    openssl enc -aes-256-cbc -pbkdf2 -salt \
        -in "$raw_file" -out "$enc_file" \
        -pass "pass:${BACKUP_ENCRYPTION_KEY}"

    # Never leave the plaintext dump on disk
    rm -f "$raw_file"

    echo "✅ $name backed up -> $enc_file"
done

# Optional: prune backups older than 30 days
find "$BACKUP_DIR" -name "*.sql.enc" -mtime +30 -delete

echo "Backup complete."
