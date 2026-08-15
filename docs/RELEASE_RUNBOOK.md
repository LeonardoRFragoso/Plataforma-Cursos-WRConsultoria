# Release Runbook

## Pre-Release Checklist

- [ ] All CI jobs green (backend, frontend, e2e, smoke, docker-config)
- [ ] Production images built and tested
- [ ] Database backup taken
- [ ] `.env.production` reviewed (no placeholders, no wildcards)
- [ ] `ENVIRONMENT=production` set
- [ ] `MERCADO_PAGO_MOCK_MODE=false`
- [ ] `E2E_TEST_MODE` not set
- [ ] `DOCS_ENABLED=false` (disable Swagger in production)
- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] `RATE_LIMIT_REDIS_URL` points to Redis
- [ ] `TRUSTED_PROXY_CIDRS` set to reverse proxy CIDR
- [ ] `TENANT_SECRET_ENCRYPTION_KEY` set (32 bytes base64)
- [ ] `SECRET_KEY` set (≥ 32 chars, not a placeholder)
- [ ] `ALLOWED_HOSTS` lists exact domains
- [ ] `CORS_ORIGINS` lists exact origins (no wildcards, no localhost)
- [ ] `VITE_API_URL` set to the correct API origin for this environment
      (build-time frontend config — changing it requires rebuilding the web
      image; never put secrets in a `VITE_*` variable)
- [ ] SMTP credentials configured (if email flows needed)
- [ ] Storage credentials configured (if video/material upload needed)

## Release Order

```
1. Backup database
2. Run migrations (one-shot container)
3. Start API + frontend + Redis + PostgreSQL
4. Verify health endpoints
5. Run legacy MP token migration (if needed)
6. Post-deploy verification
```

### 1. Backup

```bash
pg_dump -Fc -f backup_$(date +%Y%m%d_%H%M%S).dump "$DATABASE_URL"
```

Verify backup is non-empty:
```bash
ls -lh backup_*.dump
```

### 2. Migrations

```bash
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
```

If migration fails:
- DO NOT start the API
- Restore database from backup
- Investigate migration error
- Fix and re-run

### 3. Start services

```bash
docker compose -f docker-compose.prod.yml up -d
```

> **Note:** `VITE_API_URL` is baked into the frontend at image build time.
> If the API origin changed since the last build, rebuild the web image first:
> `VITE_API_URL=https://api.example.com docker compose -f docker-compose.prod.yml build web`

### 4. Health verification

```bash
curl -fsS http://localhost:8000/health/live  # liveness
curl -fsS http://localhost:8000/health/ready # readiness (DB check)
curl -fsS http://localhost/health             # frontend
```

### 5. Legacy MP token migration

Only if upgrading from a pre-SaaS version where tenants have
`mp_access_token` in `tenant.settings`:

```bash
# Dry run first
docker compose -f docker-compose.prod.yml run --rm api \
  python -m app.scripts.migrate_mp_access_tokens --dry-run

# Review output, then real run
docker compose -f docker-compose.prod.yml run --rm api \
  python -m app.scripts.migrate_mp_access_tokens
```

**Prerequisites:**
- `TENANT_SECRET_ENCRYPTION_KEY` must be set
- Script uses privileged RLS session (bypass_rls) to access all tenants

**Verification:**
- Script reports `migrated` count
- No `errors` in report
- Tenant secrets accessible via `GET /api/v1/secrets/mp_access_token`

**Rollback:**
- Tokens remain in `tenant.settings` until migration succeeds
- If migration fails partway, re-run (idempotent)
- If `TENANT_SECRET_ENCRYPTION_KEY` is lost, encrypted secrets are unrecoverable

### 6. Post-deploy verification

| Check | How |
|-------|-----|
| Admin login | `POST /api/v1/auth/login` with admin credentials |
| Student login | `POST /api/v1/auth/login` with student credentials |
| Tenant A storefront | `GET /` with tenant Host header |
| Tenant B storefront | `GET /` with different tenant Host header |
| Course catalog | `GET /api/v1/courses` |
| Certificate validation | `GET /api/v1/certificates/validate/{code}` |
| SUPER_ADMIN access | `GET /api/v1/super-admin/tenants` |
| Custom domain | `GET /` with custom domain Host header |
| Payment (staging) | Test purchase with MP sandbox credentials |

## Rollback

### Application rollback

```bash
# Stop current version
docker compose -f docker-compose.prod.yml down

# Revert to previous image
docker tag wr-api:prev wr-api:prod
docker tag wr-web:prev wr-web:prod

# Start previous version
docker compose -f docker-compose.prod.yml up -d
```

### Database rollback

**If migration added columns/tables (non-destructive):**
- Previous app version may work with new schema (backward compatible)
- Downgrade migration: `alembic downgrade -1`

**If migration was destructive (dropped columns/tables):**
- Restore from backup:
```bash
pg_restore -d "$DATABASE_URL" -c backup_YYYYMMDD_HHMMSS.dump
```

### Rollback decision matrix

| Scenario | Action |
|----------|--------|
| App bug, no schema change | Revert image only |
| Migration backward compatible | Revert image, keep schema |
| Migration destructive | Revert image + restore DB |
| Data corruption | Restore DB + revert image |

## Mercado Pago Production Checklist

- [ ] `MERCADO_PAGO_MOCK_MODE=false`
- [ ] Tenant MP access token stored in `TenantSecret` (not `tenant.settings`)
- [ ] Webhook URL is public HTTPS: `https://api.example.com/api/v1/payments/webhook/mercado-pago`
- [ ] `external_reference` = enrollment_id (used for reconciliation)
- [ ] Redirect URLs configured (`FRONTEND_URL/payment/success`, etc.)
- [ ] Idempotency: webhook handles duplicate notifications safely
- [ ] No MP credentials in logs
- [ ] Payment status flow: pending → approved/rejected
- [ ] Reconciliation: webhook updates Payment + Enrollment status

## Email Checklist

- [ ] SMTP credentials configured (`SMTP_SERVER`, `SMTP_USER`, `SMTP_PASSWORD`)
- [ ] Password reset flow sends email (currently returns token in dev mode)
- [ ] Activation flow sends email
- [ ] No real emails sent during staging tests (use mock SMTP or Mailtrap)

## Storage Checklist

- [ ] S3-compatible endpoint configured (`STORAGE_ENDPOINT`)
- [ ] Credentials configured (`STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`)
- [ ] Bucket exists (`STORAGE_BUCKET`)
- [ ] CORS configured on bucket for frontend origin
- [ ] Signed URL expiration set (`STORAGE_WATCH_URL_EXPIRATION`)
- [ ] File size limits enforced at reverse proxy level
