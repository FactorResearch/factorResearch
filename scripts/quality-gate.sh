#!/usr/bin/env bash
set -euo pipefail

export APP_SKIP_STARTUP=1
export APP_FEATURE_FLAG=V1

PROTECTED_PYTHON=(
  codes/core/ports.py
  codes/composition.py
  codes/data/providers/sec_universe.py
  codes/services/product_analytics.py
  codes/app_modules/analytics_context.py
  codes/app_modules/composition.py
  scripts/check-architecture.py
  scripts/check-duplication.py
  scripts/architecture-report.py
  tests/test_issue_076_architecture.py
  tests/test_issue_077_migrations.py
)

ruff check "${PROTECTED_PYTHON[@]}"
ruff format --check "${PROTECTED_PYTHON[@]}"
mypy
python scripts/check-architecture.py
python scripts/check-duplication.py
python scripts/architecture-report.py --check --output /tmp/architecture-report.json
