#!/usr/bin/env bash
set -euo pipefail

export APP_SKIP_STARTUP=1
export APP_FEATURE_FLAG=V1

python -m compileall -q codes scripts
python -c "import codes.app"
python -m pip_audit -r requirements.txt --strict
./scripts/quality-gate.sh
PYTHONPATH=. python scripts/generate-design-tokens.py
git diff --exit-code -- assets/style/_design_tokens.generated.scss
PYTHONPATH=. python scripts/check-design-system.py
node --check assets/iiq.js
node --check assets/legal_pages.js
node --check scripts/audit-accessibility.mjs
mkdir -p /tmp/factorresearch-css
npx --no-install sass assets/style.scss /tmp/factorresearch-css/style.css
npx --no-install sass assets/company_analysis.scss /tmp/factorresearch-css/company_analysis.css
npx --no-install sass assets/error_pages.scss /tmp/factorresearch-css/error_pages.css
diff -u assets/style.css /tmp/factorresearch-css/style.css
diff -u assets/company_analysis.css /tmp/factorresearch-css/company_analysis.css
diff -u assets/error_pages.css /tmp/factorresearch-css/error_pages.css
PYTHONPATH=. coverage run --source=codes -m pytest -q
coverage json -o /tmp/coverage.json
coverage report --skip-empty
git diff --check
