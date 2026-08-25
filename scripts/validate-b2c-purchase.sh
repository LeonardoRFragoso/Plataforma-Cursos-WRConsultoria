#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf '\n==> %s\n' "$1"
}

log "Backend: syntax + lint + migration head"
cd "$ROOT_DIR/api"
python -m compileall -q app
if command -v ruff >/dev/null 2>&1; then
  ruff check app tests
else
  python -m ruff check app tests
fi
alembic heads

log "Backend: focused B2C purchase/payment/email/financial tests"
pytest -q \
  tests/test_b2c_purchase_lifecycle.py \
  tests/test_checkout_idempotency.py \
  tests/test_payment_reconciliation.py \
  tests/test_b2c_transactional_emails.py \
  tests/test_transactional_notification_urls.py \
  tests/test_email_service_hardening.py \
  tests/test_financial_lifecycle.py \
  tests/test_asaas_financial_events.py

if [[ "${FULL_BACKEND:-0}" == "1" ]]; then
  log "Backend: full suite"
  pytest -q
fi

log "Frontend: lint + focused unit tests + production build"
cd "$ROOT_DIR/web"
npm run lint
npm run test:run -- \
  src/__tests__/views/CourseDetail.spec.js \
  src/__tests__/views/PaymentReturn.spec.js
npm run build

if [[ "${FULL_FRONTEND:-0}" == "1" ]]; then
  log "Frontend: full Vitest suite"
  npm run test:run
fi

if [[ "${E2E:-0}" == "1" ]]; then
  log "Frontend: B2C Playwright entry + purchase smoke"
  npx playwright test \
    --project=ui-mocked \
    e2e/ui-mocked/b2c-entry.spec.js \
    e2e/ui-mocked/b2c-purchase.spec.js
fi

printf '\nB2C purchase + financial lifecycle validation completed successfully.\n'
