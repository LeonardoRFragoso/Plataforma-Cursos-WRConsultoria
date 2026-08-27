# WR Catalog Production Deployment

## Summary

This document records the production deployment of the reconciled WR course
catalog, derived from OCR analysis of 47 unique PDF apostilas.

## Git State

| Item | Value |
|------|-------|
| origin/main (before) | `df00b00e30527f6b5c04cdcb99b002c2b714a13f` |
| origin/main (after)  | `0633081` (see `git log` for full SHA) |
| Backup branch        | `backup/catalog-reconciliation-pre-production` |

## Audit

| Check | Result |
|-------|--------|
| PDFs in Git | 0 |
| Full OCR text in Git | 0 |
| Secrets in Git | 0 |
| .gitignore updated | Yes (*.pdf, *.mp4, *.mp3, /uploads/, /apostilas/) |

## Pre-Deploy Tests

| Gate | Result |
|------|--------|
| ruff | All checks passed |
| Backend pytest | 773 passed |
| Frontend eslint | 0 errors |
| Frontend vitest | 387 passed |
| Frontend build | OK (3.96s) |

## Migrations

| Item | Value |
|------|-------|
| Alembic before | `f8a9b0c1d2e3` |
| Alembic after  | `e8f9a0b1c2d3` (head) |
| Heads | 1 (single head) |
| Schema migration | `d7e8f9a0b1c2` (course_content_profiles, course_materials) |
| Data migration   | `e8f9a0b1c2d3` (reconcile catalog) |

### Migration ID Note

The original migration IDs (`a1b2c3d4e5f6`, `b2c3d4e5f6a7`) collided with
existing migrations in the repository. They were renamed to
`d7e8f9a0b1c2` and `e8f9a0b1c2d3` before deployment.

## Backup

| Item | Value |
|------|-------|
| Timestamp | 2026-08-26 19:24 |
| File | `/home/leonardo/backups/wr-cursos/production-post-catalog-deploy-20260826.json` |
| Size | 47 KB |
| SHA-256 | `a016df88f2c8aa3f680172e4643327821ad6e685bda192dc8a9c3400b63a00e1` |
| Format | JSON (asyncpg export, 30 tables) |
| Location | Local filesystem (not committed) |

### Pre-State Counts

| Table | Count |
|-------|-------|
| tenants | 2 |
| courses | 33 (30 WR + 3 alfa) |
| classes | 6 |
| students | 4 |
| enrollments | 6 |
| payments | 7 |
| certificates | 2 |
| lessons | 0 |
| lesson_progress | 0 |
| course_content_profiles | 0 |
| course_materials | 0 |

## Railway Auto-Migrate

The Dockerfile CMD runs `alembic upgrade head && uvicorn ...`, so every
deploy automatically applies pending migrations. The backup was taken
after the first deploy (which applied the schema migration). The data
migration was then applied via the importer script.

## Storage

| Item | Value |
|------|-------|
| Provider configured | S3 (STORAGE_BACKEND=s3) |
| Credentials in production | NOT SET |
| Bucket | `wr-videos` (default, not provisioned) |
| Status | **BLOCKED** — no persistent private storage configured |

### Impact

CourseMaterial records were NOT created. The 47 PDF apostilas were NOT
uploaded. This is a STOP CONDITION per the deployment plan — PDFs must
not be stored on Railway's ephemeral filesystem.

### Required Action from CEO

To enable apostila uploads, the following environment variables must be
set in Railway:

- `STORAGE_ENDPOINT` — S3-compatible endpoint URL
- `STORAGE_ACCESS_KEY` — access key
- `STORAGE_SECRET_KEY` — secret key
- `STORAGE_BUCKET` — bucket name (must be private, not public-read)

Once configured, the importer can be re-run with `--apply` to upload
the 47 PDFs and create CourseMaterial records.

## Importer Execution

### Dry-Run (first pass)

| Action | Count |
|--------|-------|
| CREATE_COURSE | 20 (UPDATE→CREATE fallback) |
| DEACTIVATE_COURSE | 3 (NR-10, NR-12, NR-35) |
| CREATE_CONTENT_PROFILE | 27 |
| CONFLICT | 27 (CREATE action, code already exists) |
| REVIEW_REQUIRED | 47 |

### Apply

| Action | Count |
|--------|-------|
| CREATE_COURSE | 20 |
| DEACTIVATE_COURSE | 3 |
| CREATE_CONTENT_PROFILE | 47 |
| CONFLICT | 27 (informational) |
| REVIEW_REQUIRED | 47 |

### Idempotency Check (second dry-run)

| Action | Count |
|--------|-------|
| CREATE_COURSE | 0 |
| DEACTIVATE_COURSE | 0 |
| UPDATE_CONTENT_PROFILE | 47 (no-op, same data) |

## Post-Apply Production State

| Metric | Count |
|--------|-------|
| Active WR courses | 47 |
| Inactive WR courses | 3 (NR-10, NR-12, NR-35) |
| Content profiles | 47 |
| Course materials | 0 (storage not configured) |
| Courses without profile | 0 |
| Enrollments (WR) | 2 (preserved) |
| Certificates (WR) | 1 (preserved) |
| Payments (WR) | 2 (preserved) |

## Rollback Plan

1. **Database restore**: Use the JSON backup to restore individual tables
   if needed. The backup contains all 30 tables with full row data.
2. **Forward fix preferred**: If an issue arises, prefer a forward-only
   fix (new migration or importer correction) over Alembic downgrade.
3. **Course reactivation**: The 3 deactivated courses (NR-10, NR-12,
   NR-35) can be reactivated via admin API or SQL if needed — they are
   not deleted, only `is_active=false`.

## Deployment Verification

### Railway (Backend)

| Check | Result |
|-------|--------|
| https://wr-api-production.up.railway.app/health/live | 200 OK |
| https://wr-api-production.up.railway.app/health/ready | 200 OK (db_latency 2-6ms) |
| Public courses API | 200 OK, 47 active + 3 inactive |
| Content profile API | 200 OK, fully populated |
| Tenant isolation | WR sees 47, alfa sees 3, untrusted origin rejected (400) |

### Vercel (Frontend)

| Check | Result |
|-------|--------|
| https://wr-cursos-demo.vercel.app/ | 200 OK |
| https://wr-cursos-demo.vercel.app/cursos | 200 OK |
| Build | Ready in 1m |
| Alias | https://wr-cursos-demo.vercel.app |

## Variant Families Validated

| NR | Variants |
|----|----------|
| NR-10 | 2 (Básico, SEP) |
| NR-11 | 6 (Empilhadeira, Guindauto, Mini Carregadeira, Plataforma, Ponte, Retroescavadeira) |
| NR-17 | 4 (Administrativo, Checkout, Telemarketing, Transporte Manual) |
| NR-20 | 6 (Inicial, Básico, Intermediário, Avançado I, Avançado II, Específico) |
| NR-26 | 2 (Geral, Laboratório) |
| NR-29 | 3 (Portuário, CPATP, Sinaleiro) |
| NR-31 | 4 (Periódico, Agrotóxicos, CIPATR, Admissional) |
| NR-33 | 2 (Autorizado, Supervisor) |
| NR-34 | 2 (Admissional, Periódico) |

## Pending Items

1. **Storage configuration**: S3 credentials needed to upload 47 PDFs
   and create CourseMaterial records.
2. **Review required**: All 47 content profiles have `review_status=INFERRED`
   with missing metadata fields (target_audience, workload, modality,
   assessment, validity, etc.) that were not available in the PDFs.
   These require manual review by the academic team.
3. **Course materials**: 0 of 47 PDFs uploaded (blocked by storage).
