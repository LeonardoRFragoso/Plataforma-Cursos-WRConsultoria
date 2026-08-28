# AGENTS.md — WR Plataforma Cursos

## Project Commands

### Frontend (web/)

```bash
cd web
npx vitest run                              # unit tests
npx playwright test --project=ui-mocked     # E2E mocked tests
npm run lint && npm run build               # lint + build gates
```

### Backend (api/)

```bash
cd api
# Lint
venv/bin/python -m ruff check app/ tests/
# Alembic heads check (must be exactly 1 head)
venv/bin/python -m alembic heads
# Tests (use isolated DB to avoid concurrent test races)
WR_TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos_test_cert" \
  venv/bin/python -m pytest tests/ -q --no-cov
```

### Production Deploy

- **Frontend**: Vercel auto-deploys `main` to production. Verify with
  `vercel ls wr-cursos-demo` and check the production alias is the latest SHA.
- **Backend**: Railway auto-deploys `main` to `wr-api` service. The run
  command is `alembic upgrade head && uvicorn app.main:app`. Verify with
  `railway status` and `curl https://wr-api-production.up.railway.app/health/ready`.
- **DB access**: `railway connect Postgres` (opens psql via SSH tunnel).
- **Container exec**: `railway ssh --service wr-api "<command>"`.

### Tutor NR Knowledge Ingestion

```bash
# In the Railway container (via railway ssh --service wr-api):
cd /app && TUTOR_KNOWLEDGE_DIR=/tmp/tutor-knowledge \
  DATABASE_URL='postgresql+asyncpg://postgres:...@postgres.railway.internal:5432/railway' \
  python -m app.scripts.ingest_nr_tutor_knowledge --apply
```

The knowledge files (15 NR `extracted-text.md`) live in
`/home/leonardo/dev/Cursos-WR/analysis/<nr-slug>/extracted-text.md` and
must be piped into the container via SSH (no volume mount in production).

## P0 Production Boot Fix (PR #41 + idempotent migrations)

### White Screen Root Cause

The router guard in `web/src/router/index.js` awaited
`authStore.initializeUser()` (which calls `/auth/me`) for **all** routes,
including public ones. With a stale token in localStorage, this blocked
the entire SPA boot for up to 16 seconds (token refresh retries + timeout).

### White Screen Fix

1. **Router guard**: only `await initializeUser()` for authenticated routes;
   public routes render immediately and session restoration runs in the
   background (`web/src/App.vue`).
2. **Axios client** (`web/src/api/client.js`): 15s `REQUEST_TIMEOUT`,
   no recursive token refresh on `/auth/refresh` itself.
3. **Boot state** (`web/index.html`): inline spinner + non-blocking Google
   Fonts so the user sees content immediately on first paint.
4. **Result**: white screen with stale token dropped from ~16s to <0.4s.

### Backend Crash Root Cause

Alembic detected two head revisions branching from `h6c7d8e9f0a1`:
`i7c8d9e0f1a2` (compliance) and `i9d0e1f2a3b4` (tutor RAG). Railway's
`alembic upgrade head` failed with "Multiple head revisions" and the
service crashed on every deploy.

### Backend Crash Fix

1. **Merge migration** `3f273adccf42` unifies the two heads.
2. **Idempotent migrations**: the tutor RAG and compliance migrations now
   use `DO $$ ... $$` blocks for enum creation (checkfirst=True is
   unreliable with asyncpg), `has_table()` checks before `create_table`,
   and `DROP IF EXISTS` before `CREATE` for triggers/policies. This
   handles the production DB's partially-applied state (enum type existed
   but tables/migration record were missing from a previous crashed deploy).

### Regression Tests

- `web/src/__tests__/router.spec.js` — public routes don't block on `/auth/me`
- `web/src/__tests__/api/client.spec.js` — timeout + no recursive refresh
- `web/e2e/ui-mocked/boot-white-screen.spec.js` — boot time under slow API

## Known Vulnerabilities (npm audit, dev-only)

13 vulnerabilities in dev dependencies — all require breaking upgrades:
- `esbuild <=0.24.2` (moderate) → needs vite@8 major
- `happy-dom <=20.8.8` (critical) → needs happy-dom@20.11.12 major
- `minimatch 9.0.0-9.0.6` (high) → transitive via @typescript-eslint

None affect the production build output. Scheduled for a future dependency
upgrade cycle.

### Python (pip-audit)

API dependencies with known vulnerabilities requiring major upgrades:
- `starlette 0.27.0` → needs 1.x (breaking, tied to FastAPI upgrade)
- `fastapi 0.104.1` → needs 0.109.1+ (breaking)
- `cryptography 44.0.3` → needs 46.x+
- `jinja2 3.1.2` → needs 3.1.6+
- `python-multipart 0.0.6` → needs 0.0.26+
- `requests 2.31.0` → needs 2.32.4+
- `python-jose 3.3.0` → needs 3.4.0+
- `pytest 7.4.3` → needs 9.0.3+ (dev-only)

Scheduled for a separate security upgrade cycle to avoid breaking changes
in this hardening PR.

---

## Tutor NR Retrieval Quality (PR #42)

### Root Cause

`plainto_tsquery` uses AND semantics (`&`) in PostgreSQL FTS, which caused
poor retrieval for natural language questions. The `_build_fts_query`
function correctly built an OR-based query but it was never used in the
SQL query — the code called `plainto_tsquery` directly.

### Fix

1. **Hybrid retrieval** (`api/app/services/tutor/retrieval.py`): OR-based
   `to_tsquery` with prefix matching (`:*`), ILIKE exact term matching,
   heading boost, FTS rank capping, diversity selection, and scope-only
   fallback.
2. **Aliases/synonyms** (`api/app/services/tutor/aliases.py`): semantic
   synonyms for query expansion (e.g., "trator" → retroescavadeira).
3. **Scope disambiguation** (`api/app/services/tutor/scope.py`):
   word-boundary matching to prevent false positives from substring matches.
4. **Conversation context**: follow-up questions use prior turns for
   query expansion (e.g., "E quem pode trabalhar nele?" after "O que é SEP?").

### Validation

- 83-case golden dataset across all 15 NR materials
- 100% Top-1 accuracy, 0% wrong-variant rate
- Evaluation script: `api/app/scripts/eval_tutor_retrieval.py`
- Golden dataset: `analysis/tutor/golden-retrieval-cases.json`
- Test suite: `api/tests/test_tutor_knowledge.py` (27 tests including
  6 critical queries + follow-up context test)

### Backend Test Fixes (14 failures → 0)

- **Certificate 200 vs 201**: `regulatory_legacy_guards.py` registered a
  guard route for `POST /certificates/` before the actual certificates
  router. The guard route lacked `status_code=201` and
  `response_model=CertificateResponse`.
- **CNPJ validation**: `tests/conftest.py` now has `make_valid_cnpj()`
  helper. Identity security tests were generating random CNPJs that
  failed strict check-digit validation.

### E2E Test Fixes (5 failures → 0)

- **Tutor NR tests**: need `localStorage` token setup for router guard
- **Strict mode**: use `getByTestId('tutor-source-chip').filter({ hasText })`
  instead of generic text locators
- **Compliance operations**: expand "Operações" nav group before clicking

---

## Certificate QR Validation & Demo Mode

## STATUS

**TECHNICAL CERTIFICATE FOUNDATION — DEMO ONLY**

This is the technical foundation for verifiable certificates (QR codes,
public validation, academic journey, content hash, demo mode). The PDF
template is a **DEMO template** and carries the "SEM VALIDADE OFICIAL"
watermark. No official/regulatory certificate is issued by this code.

**REGULATORY TEMPLATE PENDING NR-01 AUDIT.**

The certificate layout and fields are NOT regulatorily complete. A separate
audit against NR-01 item 1.7 (especially 1.7.1.1 and Anexo II for EAD/
semipresencial) is in progress. Regulatory fields will be added to
`CertificatePDFContext` only after the audit confirms requirements — no
fake or speculative values are present.

## Feature Summary

Verifiable certificates with QR codes, enriched public validation, demo mode,
and an auditable academic journey — implemented in an isolated worktree
`feat/certificate-demo-qr-trace` to avoid interfering with parallel development.

## Key Files

- `api/app/services/certificate_service.py` — QR generation, visual PDF,
  demo mode, journey aggregation, refactored issuance
- `api/app/schemas/certificate.py` — enriched validation response, journey,
  nested course/student summaries
- `api/app/api/routes/certificates.py` — fixed validation URL, enriched
  validate endpoint, privacy-safe response
- `api/app/scripts/create_demo_certificate.py` — idempotent demo cert generator
- `web/src/views/ValidateCertificate.vue` — auto-validation via `?codigo=`,
  status differentiation, demo banner, journey timeline
- `web/src/components/CertificateDetails.vue` — expandable student/course/
  journey/integrity details

## Test Commands

### Backend (use isolated DB to avoid concurrent test races)

```bash
cd api
WR_TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos_test_cert" \
  venv/bin/python -m pytest tests/test_certificate_qr_validation_demo.py tests/test_certificates.py tests/test_certificates_unit.py tests/test_certificate_tenant_isolation.py -q --no-cov
```

### Frontend

```bash
cd web
npx vitest run                              # all 402 unit tests
npx playwright test --project=ui-mocked     # all 77 E2E tests
npm run lint && npm run build               # lint + build gates
```

### Backend lint

```bash
cd api && venv/bin/python -m ruff check app/ tests/
```

## Demo Certificate Generation

```bash
cd api
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/wr_demo_cert" \
  venv/bin/python -m app.scripts.create_demo_certificate --apply --course-code NR-10
```

The script is idempotent — re-running with the same course + student email
returns the existing demo certificate instead of creating a duplicate.

## Design Decisions

- **Validation URL**: `/validar-certificado?codigo=<code>` (public-friendly
  Portuguese path, not the internal API path `/certificates/validate`)
- **QR code**: encodes the full public validation URL; also rendered as
  visible text below the QR for manual entry
- **Content hash**: SHA-256 of the certificate *registry data* (not the PDF
  bytes) — stable across PDF regeneration, tamper-evident
- **Demo mode**: certificate numbers prefixed with `DEMO-`, PDF carries a
  "SEM VALIDADE OFICIAL" watermark, validation response sets `is_demo: true`
- **Privacy**: public validation response contains no CPF, email, phone,
  user IDs, or payment data — only student name, course info, and journey
- **Journey**: timeline of ENROLLED → COURSE_STARTED → LESSON_COMPLETED →
  COURSE_COMPLETED → CERTIFICATE_ISSUED, with per-lesson expandable detail
- **Status differentiation**: ACTIVE, EXPIRED, REVOKED (with reason),
  SUPERSEDED, NOT_FOUND — each with distinct UI treatment
- **Tenant isolation**: public validation by code is global (privacy-safe);
  admin certificate access is tenant-scoped (404 for cross-tenant)
- **CertificatePDFContext**: PDF rendering accepts a single dataclass
  (`CertificatePDFContext`) via `CertificateService.build_pdf(ctx)`. The
  legacy `generate_certificate_pdf(**kwargs)` signature is kept as a
  backwards-compatible wrapper. Future NR-01 regulatory fields
  (training_location, training_started_at, training_completed_at,
  training_type, program_content, instructors, instructor_qualifications,
  technical_responsible, signatures, content_reuse) are declared as
  optional fields on the context — all default to `None`, none are
  populated yet. This allows a future multi-page layout (page 1 =
  certificate, page 2 = program content/instructors) without breaking
  callers.
- **QR independence**: `build_validation_url()` is the single source of the
  QR payload, decoupled from the PDF layout. Redesigning the certificate
  does not affect validation.
