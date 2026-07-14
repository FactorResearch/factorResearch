#!/usr/bin/env bash
set -euo pipefail

export APP_SKIP_STARTUP=1
export APP_FEATURE_FLAG=V1

python -m compileall -q codes scripts
python -c "import codes.app"
node --check assets/iiq.js
node --check assets/legal_pages.js
node --check scripts/audit-accessibility.mjs
npx --no-install sass assets/style.scss /tmp/factorresearch.css --no-source-map
npx --no-install sass assets/company_analysis.scss /tmp/company_analysis.css --no-source-map
npx --no-install sass assets/error_pages.scss /tmp/error_pages.css --no-source-map
diff -u assets/style.css /tmp/factorresearch.css
diff -u assets/company_analysis.css /tmp/company_analysis.css
diff -u assets/error_pages.css /tmp/error_pages.css
PYTHONPATH=. pytest -q
git diff --check
