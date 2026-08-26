# AGENTS.md — Certificate QR Validation & Demo Mode

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
