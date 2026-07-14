#!/usr/bin/env bash
# Verifies backups are actually restorable — not just that pg_dump succeeded.
#
# For each of the 4 databases:
#   1. Find the most recent encrypted backup
#   2. Decrypt it to a temp file (never touches disk unencrypted longer than needed)
#   3. Restore into a throwaway scratch database
#   4. Run sanity checks (row counts on key tables)
#   5. Drop the scratch database
#
# Requires: BACKUP_ENCRYPTION_KEY, PGHOST/PGPORT/PGUSER/PGPASSWORD (or a
# restore-target connection URL) with CREATEDB privilege.
#
# Usage: ./scripts/restore_test.sh
# Run this on a schedule (weekly cron / CI job) — a backup you've never
# restored is not a backup, it's a hope.

set -euo pipefail

# Load config from .env (repo root, or path given via ENV_FILE). Same pattern
# as backup_db.sh — keeps local/staging runs consistent with app config.
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
RESTORE_HOST="${RESTORE_HOST:-localhost}"
RESTORE_PORT="${RESTORE_PORT:-5432}"
RESTORE_USER="${RESTORE_USER:-postgres}"

if [ -z "${BACKUP_ENCRYPTION_KEY:-}" ]; then
    echo "ERROR: BACKUP_ENCRYPTION_KEY not set." >&2
    exit 1
fi

# name -> a table expected to have rows, used as a minimal sanity check
declare -A SANITY_TABLES=(
    ["factorresearch_users"]="subscriptions"
    ["factorresearch_market"]="sec_facts_meta"
    ["factorresearch_analytics"]="analysis_snapshots"
)

FAILED=0

for db_name in "${!SANITY_TABLES[@]}"; do
    echo "=== Restore test: $db_name ==="

    latest_enc=$(find "$BACKUP_DIR" -name "${db_name}_*.sql.enc" | sort | tail -n 1)
    if [ -z "$latest_enc" ]; then
        echo "❌ No backup found for $db_name"
        FAILED=1
        continue
    fi
    echo "Using backup: $latest_enc"

    tmp_dump=$(mktemp)
    scratch_db="restoretest_${db_name}_$(date +%s)"

    # Decrypt
    if ! openssl enc -d -aes-256-cbc -pbkdf2 \
        -in "$latest_enc" -out "$tmp_dump" \
        -pass "pass:${BACKUP_ENCRYPTION_KEY}"; then
        echo "❌ Decryption failed for $db_name"
        rm -f "$tmp_dump"
        FAILED=1
        continue
    fi

    # Create scratch DB, restore into it
    createdb -h "$RESTORE_HOST" -p "$RESTORE_PORT" -U "$RESTORE_USER" "$scratch_db"
    if ! pg_restore -h "$RESTORE_HOST" -p "$RESTORE_PORT" -U "$RESTORE_USER" \
        -d "$scratch_db" --no-owner --no-privileges "$tmp_dump"; then
        echo "❌ pg_restore failed for $db_name"
        dropdb -h "$RESTORE_HOST" -p "$RESTORE_PORT" -U "$RESTORE_USER" "$scratch_db" || true
        rm -f "$tmp_dump"
        FAILED=1
        continue
    fi

    # Sanity check: expected table exists and has data
    table="${SANITY_TABLES[$db_name]}"
    row_count=$(psql -h "$RESTORE_HOST" -p "$RESTORE_PORT" -U "$RESTORE_USER" \
        -d "$scratch_db" -tAc "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "ERROR")

    if [ "$row_count" = "ERROR" ]; then
        echo "❌ Sanity check query failed for $db_name (table: $table)"
        FAILED=1
    else
        echo "✅ $db_name restored OK — $table has $row_count rows"
    fi

    # Cleanup — never leave scratch DB or plaintext dump behind
    dropdb -h "$RESTORE_HOST" -p "$RESTORE_PORT" -U "$RESTORE_USER" "$scratch_db"
    rm -f "$tmp_dump"
done

if [ "$FAILED" -ne 0 ]; then
    echo ""
    echo "⚠️  One or more restore tests FAILED. Investigate before relying on backups."
    exit 1
fi

echo ""
echo "✅ All restore tests passed."
