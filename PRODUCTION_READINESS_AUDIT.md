# Production Readiness Audit

**Date:** 2026-08-15  
**Branch:** `chore/production-readiness`  
**Base:** `f2b73ca` (main, post-merge PR #9)

## Staging Readiness Status

**READY WITH CAVEATS**

The two final pre-merge release blockers discovered in the audit of PR #10
have been resolved:

1. **P0 — Frontend production API endpoint contract.** `VITE_API_URL` is now a
   build-time argument to `web/Dockerfile.prod` (validated non-empty, exposed
   only to the builder stage). `docker-compose.prod.yml` passes it under
   `web.build.args` with a `${VITE_API_URL:?...}` required-variable contract.
   CI builds the web image with an unmistakable test URL
   (`https://api.release-test.example`) and asserts the compiled runtime
   assets contain that URL and do NOT contain the `http://localhost:8000`
   development fallback. A build without `VITE_API_URL` is proven to fail.
2. **P1 — `/health/ready` failure contract.** The readiness probe no longer
   depends on `get_db` (which executes tenant RLS setup before yielding and
   can raise before the handler's try block). It creates a dedicated
   `AsyncSession` inside its own try block and maps SQLAlchemy connectivity
   exceptions (`OperationalError`, `InterfaceError`) and `OSError` to a clean
   `503 not_ready`. Tests cover DB healthy (200), DB unavailable (503),
   `/health/live` (200, no DB query), and absence of secrets in responses.

Remaining caveats (out of scope for PR #10, tracked separately):

- Infrastructure provisioning (DNS, TLS, reverse proxy, managed Postgres/Redis)
- Real production secrets must be supplied via environment/.env
- SMTP email sending is not yet functional (forgot-password creates a token
  but does not send email) — separate email-delivery PR
- Python dependency security upgrades (fastapi, starlette, python-jose,
  python-multipart, etc.) — separate security PR

## Classification

- **P0 BLOCKER** — Must fix before staging deployment
- **P1 REQUIRED** — Must fix before production deployment
- **P2 RECOMMENDED** — Should fix before production
- **P3 OPTIONAL** — Nice to have, future improvement

---

## Findings

### Docker & Container Hardening

| # | Severity | Finding |
|---|----------|---------|
| 1 | **P0** | `docker-compose.yml` is development-only: bind mounts `./api:/app` and `./web:/app`, runs `uvicorn --reload` and `npm run dev`. Not safe for production. |
| 2 | **P0** | `api/Dockerfile` runs as root. No non-root user. No multi-stage build. Build tools (gcc) remain in runtime image. |
| 3 | **P0** | `web/Dockerfile` runs Vite dev server in production. No static build, no nginx, no SPA fallback. |
| 4 | **P1** | No production compose file exists. No `docker-compose.prod.yml`. |
| 5 | **P1** | PostgreSQL exposes port 5432 publicly in dev compose. Production must not expose DB. |
| 6 | **P1** | No Redis service in compose for rate limiting. |
| 7 | **P2** | API healthcheck uses `/docs` (Swagger). Should use dedicated health endpoint. |
| 8 | **P2** | No graceful shutdown configuration (uvicorn `--timeout-graceful-shutdown`). |

### Configuration & Secrets

| # | Severity | Finding |
|---|----------|---------|
| 9 | **P0** | `SECRET_KEY` defaults to `"your-secret-key-change-in-production"`. Application starts without failing. |
| 10 | **P0** | `TENANT_SECRET_ENCRYPTION_KEY` defaults to empty string. Falls back to deriving from SECRET_KEY. Must be explicitly set in production. |
| 11 | **P0** | `ALLOWED_HOSTS` defaults to `["*"]`. TrustedHostMiddleware allows any host. |
| 12 | **P0** | `MERCADO_PAGO_MOCK_MODE` defaults to `False` but nothing prevents `True` in production. |
| 13 | **P0** | `E2E_TEST_MODE` is only checked in the bootstrap script, not in application startup. |
| 14 | **P1** | No fail-closed validation at startup when `ENVIRONMENT=production`. `validate_secrets()` exists but only exposed via `/api/v1/health/secrets` — does not block startup. |
| 15 | **P1** | `.env.example` is behind actual config. Missing `ENVIRONMENT`, `RATE_LIMIT_*`, `TENANT_SECRET_ENCRYPTION_KEY`, `ALLOWED_HOSTS`, `E2E_TEST_MODE`. |
| 16 | **P1** | No `.env.production.example` exists. |
| 17 | **P2** | `CORS_ORIGINS` defaults include localhost origins. Production must explicitly set allowed origins. |
| 18 | **P2** | `RATE_LIMIT_ENABLED` defaults to `False`. Production should enable rate limiting. |

### Health Endpoints

| # | Severity | Finding |
|---|----------|---------|
| 19 | **P1** | No `/health/live` (liveness) endpoint. Only `/health` which checks DB. |
| 20 | **P1** | No `/health/ready` (readiness) endpoint. |
| 21 | **P2** | Swagger `/docs` is always exposed. Should be configurable/disabled in production. |
| 22 | **P2** | `/health` path is used in middleware bypass — new endpoints must be added to bypass list. |

### Reverse Proxy & Rate Limiting

| # | Severity | Finding |
|---|----------|---------|
| 23 | **P0** | Rate limiter uses `request.client.host` which behind a reverse proxy returns the proxy IP, not the client IP. All clients would share a single rate limit bucket. |
| 24 | **P1** | No `TRUSTED_PROXY` configuration. No safe X-Forwarded-For handling. |
| 25 | **P2** | No reverse proxy / TLS termination configuration documented. |

### Logging & Observability

| # | Severity | Finding |
|---|----------|---------|
| 26 | **P1** | No structured logging. No request correlation ID. No logging middleware. |
| 27 | **P2** | No request latency logging. |
| 28 | **P2** | No tenant identifier in logs. |

### Database & Migrations

| # | Severity | Finding |
|---|----------|---------|
| 29 | **P1** | No documented migration strategy. No runbook for upgrade/rollback. |
| 30 | **P2** | DB engine has no explicit `pool_size` or `max_overflow`. Default pool size (5) may be insufficient for multi-worker deployment. |
| 31 | **P2** | No migration backup strategy documented. |

### Email

| # | Severity | Finding |
|---|----------|---------|
| 32 | **P1** | Password reset email is NOT sent. Code comment says "Envio de e-mail omitido para simplicidade". Token is returned directly in dev mode. |
| 33 | **P2** | No email templates. No activation email flow. |
| 34 | **P2** | `aiosmtplib` is in requirements but no EmailService implementation exists. |

### Storage

| # | Severity | Finding |
|---|----------|---------|
| 35 | **P2** | S3-compatible storage is configured but no production bucket/credentials documented. |
| 36 | **P2** | No documented CORS configuration for storage provider. |
| 37 | **P3** | No file size constraints documented. |

### Mercado Pago

| # | Severity | Finding |
|---|----------|---------|
| 38 | **P1** | No production payment runbook. No webhook URL documentation. |
| 39 | **P1** | No idempotency documentation for webhook. |
| 40 | **P2** | No logging of payment events (without credentials). |

### Custom Domains

| # | Severity | Finding |
|---|----------|---------|
| 41 | **P1** | Custom domain verification lifecycle exists in code but no infrastructure documentation (DNS, TLS, reverse proxy, wildcard). |
| 42 | **P1** | TenantResolver depends on Host header. No documentation of ingress requirements for Host preservation. |

### Security

| # | Severity | Finding |
|---|----------|---------|
| 43 | **P0** | No HTTPS enforcement. No HSTS. No security headers. |
| 44 | **P1** | `/api/v1/health/secrets` endpoint exposes configuration validation results. Should not be publicly accessible in production. |
| 45 | **P2** | No request size limits for file uploads. |

### CI/CD

| # | Severity | Finding |
|---|----------|---------|
| 46 | **P1** | CI does not build or validate production images. |
| 47 | **P2** | No dependency security audit in CI. |
| 48 | **P3** | No image publishing to registry. |

### Documentation

| # | Severity | Finding |
|---|----------|---------|
| 49 | **P1** | No `docs/DEPLOYMENT.md`. |
| 50 | **P1** | No `docs/RELEASE_RUNBOOK.md`. |
| 51 | **P1** | No `docs/BACKUP_RESTORE.md`. |
| 52 | **P2** | Existing docs (ARCHITECTURE.md, MULTI_TENANT_ARCHITECTURE.md, etc.) are outdated relative to SaaS completion. |
| 53 | **P2** | No CHANGELOG entry for SaaS completion. |

### GitHub Governance

| # | Severity | Finding |
|---|----------|---------|
| 54 | **P1** | `main` branch has no protection rules. Direct push is possible. |

---

## Summary by Severity

| Severity | Count |
|----------|-------|
| P0 BLOCKER | 10 |
| P1 REQUIRED | 18 |
| P2 RECOMMENDED | 16 |
| P3 OPTIONAL | 2 |
| **Total** | **46** |

## P0 Blockers (must fix before staging)

1. Dev-only docker-compose with bind mounts + --reload
2. API Dockerfile runs as root
3. Web Dockerfile runs Vite dev server
4. SECRET_KEY placeholder allowed in production
5. TENANT_SECRET_ENCRYPTION_KEY empty allowed in production
6. ALLOWED_HOSTS wildcard allowed in production
7. MERCADO_PAGO_MOCK_MODE=true allowed in production
8. E2E_TEST_MODE not checked at app startup
9. Rate limiter uses proxy IP behind reverse proxy
10. No HTTPS enforcement / security headers

## Remediation Plan

This audit will be addressed in atomic commits on `chore/production-readiness`:

1. `docs(release): add production readiness audit` — this file
2. `build(api): add hardened production container` — `api/Dockerfile.prod`
3. `build(web): add static production frontend image` — `web/Dockerfile.prod` + nginx
4. `build(deploy): add production-like compose configuration` — `docker-compose.prod.yml`
5. `fix(config): fail closed on unsafe production settings` — startup validation
6. `feat(health): separate liveness and readiness probes` — `/health/live`, `/health/ready`
7. `fix(proxy): trust forwarded client IP only from configured proxies` — `TRUSTED_PROXY`
8. `feat(observability): add safe request correlation logging` — structured logging middleware
9. `docs(ops): add deployment backup and rollback runbooks` — `docs/`
10. `test(release): validate production images and smoke flow` — CI job
11. `docs(platform): reconcile documentation after SaaS merge` — update existing docs

## Final Pre-Merge Reconciliation (PR #10)

Two production-readiness gaps discovered in the final audit were corrected in
atomic commits on the same branch:

12. `fix(web): inject API endpoint into production build` — `VITE_API_URL`
    build-time contract (`web/Dockerfile.prod` ARG validation +
    `docker-compose.prod.yml` `web.build.args`)
13. `fix(health): make readiness fail cleanly on database outage` — dedicated
    readiness DB probe, 503 on connectivity failure, no `get_db` dependency
14. `test(release): verify production artifact configuration` — CI asserts the
    compiled frontend bundle embeds the correct API URL and not the dev
    fallback; production-mode API container smoke (`/health/live` 200,
    `/docs` 404 with `DOCS_ENABLED=false`); prod compose config validated
    with release-test env values
15. `docs(release): clarify frontend build-time configuration` —
    `.env.production.example`, `docs/DEPLOYMENT.md`, `docs/RELEASE_RUNBOOK.md`,
    and this audit updated to document the build-time `VITE_API_URL` contract
