#!/usr/bin/env bash
set -euo pipefail

PROCESS_ROLE=migration python scripts/check-production-config.py
PROCESS_ROLE=migration python -m codes.data.migrate
