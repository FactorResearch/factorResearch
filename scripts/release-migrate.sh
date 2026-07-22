#!/usr/bin/env bash
set -euo pipefail

PROCESS_ROLE=migration python scripts/check-production-config.py
PROCESS_ROLE=migration python -m codes.data.migrate
if [ -n "${LEGACY_PORTFOLIO_USER_IDS_FILE:-}" ]; then
  PROCESS_ROLE=migration python -m codes.data.migrate_portfolios \
    --user-file "$LEGACY_PORTFOLIO_USER_IDS_FILE"
fi
