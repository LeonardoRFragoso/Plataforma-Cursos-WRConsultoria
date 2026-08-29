# Observability Guide

## Current State

### LMS (Plataforma de Cursos)

- **Structured logging:** Implemented via `RequestLoggingMiddleware`
  and `setup_logging()` in `app/core/logging_config.py`
- **Health checks:** `/health` (liveness) and `/health/ready` (readiness)
- **Secrets audit:** `/api/v1/health/secrets` (non-production only)
- **Rate limiting:** Enabled in production (`RATE_LIMIT_ENABLED=true`)
- **External monitoring:** Not configured (Railway logs only)

### Central WR

- **Structured logging:** Not yet implemented (ad-hoc `logging.getLogger`)
- **Health checks:** `/health` (liveness) and `/ready` (readiness)
- **Rate limiting:** Not yet implemented
- **External monitoring:** Not configured (Railway logs only)

## P0 Events That Must Generate Alerts

The following events are critical and should trigger immediate
notification when a monitoring provider is connected:

### Backend down

- **Detection:** Health check failure (`/health` or `/health/ready` returns non-200)
- **Severity:** P0
- **Action:** Check Railway service status, restart if needed

### Database unavailable

- **Detection:** `/health/ready` returns 503 (database ping fails)
- **Severity:** P0
- **Action:** Check Railway Postgres status, verify connection pool

### LMS B2B failures

- **Detection:** Central WR academic endpoints return 502/503 repeatedly
- **Severity:** P1
- **Action:** Check LMS backend health, B2B client credentials, network

### Payment webhook failures

- **Detection:** `PaymentWebhookEvent` records with `FAILED` state
- **Severity:** P1
- **Action:** Check Asaas webhook configuration, API key validity

### Email delivery failures

- **Detection:** `EmailServiceError` exceptions in logs
- **Severity:** P2
- **Action:** Check SMTP credentials, provider status

### Certificate signing failures

- **Detection:** `CertificateSigningJob` records with `FAILED` status
- **Severity:** P1
- **Action:** Check PAdES gateway availability, signing profile validity

## Recommended Monitoring Provider

When authorized, connect one of the following:

### Sentry (recommended for error tracking)

- Free tier: 5,000 errors/month
- Captures unhandled exceptions with stack traces
- DSN configuration via environment variable

### Better Stack / UptimeRobot (for uptime monitoring)

- Free tier available
- Monitor `/health` and `/health/ready` endpoints
- Alert on non-200 responses

### Railway built-in metrics

- CPU, memory, and request metrics available in Railway dashboard
- No additional configuration needed

## Log Format

### LMS (structured JSON in production)

```json
{
  "timestamp": "2026-08-29T12:00:00Z",
  "level": "INFO",
  "request_id": "abc-123",
  "method": "GET",
  "path": "/api/v1/dashboard",
  "status": 200,
  "duration_ms": 45,
  "tenant_id": "11111111-1111-1111-1111-111111111111"
}
```

### What is NEVER logged

- Passwords (plaintext or hashed)
- Authorization headers / Bearer tokens
- JWT payloads (full)
- SSO secrets / B2B secrets
- API keys (Asaas, Mercado Pago, etc.)
- CPF (full — only masked/last 3 digits if needed)
- SMTP passwords
- Tenant secret encryption keys
