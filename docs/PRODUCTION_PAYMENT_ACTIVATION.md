# Production Payment Activation Runbook

This document describes the steps required to activate real payment
processing via Asaas. **Do NOT execute these steps without explicit
authorization from the CEO/finance team.**

## Prerequisites

- Asaas account created (production environment)
- Production API key (`$aact_prod_...`) obtained from Asaas dashboard
- LMS backend deployed and accessible at a public HTTPS URL
- `PAYMENT_PROVIDER=ASAAS` set in Railway environment variables

## Activation Checklist

### 1. Set environment variables in Railway (LMS `wr-api` service)

```
PAYMENT_PROVIDER=ASAAS
ASAAS_MOCK_MODE=false
ASAAS_WEBHOOK_BASE_URL=https://wr-api-production.up.railway.app
```

> **Note:** `MERCADO_PAGO_MOCK_MODE` can remain `true` — it is no longer
> validated when `PAYMENT_PROVIDER=ASAAS`.

### 2. Register the Asaas API key via the admin UI

- Log in as ADMIN
- Navigate to Integrations → Asaas
- Click "Connect"
- Paste the production API key (`$aact_prod_...`)
- The backend validates the key format and tests the connection

### 3. Validate the environment

- Confirm `/api/v1/integrations/asaas/status` returns:
  - `configured: true`
  - `connection_valid: true`
  - `is_asaas_active: true`

### 4. Configure the webhook

- Call `POST /api/v1/integrations/asaas/webhook/setup` to register
  the webhook URL with Asaas
- Confirm `webhook_configured: true` and `webhook_enabled: true`

### 5. Validate webhook signature

- Asaas sends a `asaas_webhook_token` header
- The backend validates it via `hmac.compare_digest` against the
  per-tenant webhook token stored in `TenantSecret`
- Verify with a test event from the Asaas dashboard

### 6. Execute a controlled test transaction

- Create a test enrollment with a real (small) amount
- Process a PIX payment
- Confirm the webhook fires and the payment status updates to `APROVADO`
- Confirm the enrollment transitions to `CONFIRMADA`

### 7. Validate reconciliation

- Check `PaymentWebhookEvent` records for idempotency
- Verify duplicate webhook events do not create duplicate payments
- Confirm `reconcile_payment_status` runs correctly

### 8. Switch to production

- Set `ENVIRONMENT=production` in Railway
- The `validate_production_config()` validator will enforce:
  - `ASAAS_MOCK_MODE=false` ✓
  - `ASAAS_WEBHOOK_BASE_URL` set ✓
  - `EMAIL_MOCK_MODE=false` (if EMAIL_ENABLED=true) ✓
  - All other production hardening checks ✓

## Rollback

If issues occur:
1. Set `ASAAS_MOCK_MODE=true` (reverts to mock)
2. Set `PAYMENT_PROVIDER=MERCADO_PAGO` (reverts to legacy)
3. Set `ENVIRONMENT=staging`
4. Investigate root cause before retrying

## Security Notes

- API keys are stored encrypted in `TenantSecret` (write-only)
- Webhook tokens are per-tenant and validated with constant-time comparison
- No credentials are ever returned in API responses
- No credentials are logged in plaintext
