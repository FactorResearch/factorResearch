#!/usr/bin/env bash
set -euo pipefail

python scripts/check-production-config.py
python -m codes.data.migrate
