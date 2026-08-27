# Course Material Storage Pipeline

## Overview

The WR Cursos platform uses a presigned-upload flow for course materials
(apostilas, manuals, etc.). Files are stored in a private S3-compatible
bucket and accessed via short-lived presigned URLs. No files pass through
the FastAPI backend — uploads go directly to storage.

## Architecture

```
Admin Browser                FastAPI Backend              S3-Compatible Storage
    │                             │                            │
    │  1. Select PDF + SHA-256    │                            │
    │────────────────────────────>│                            │
    │  2. POST /upload-url        │                            │
    │     (filename, sha, size)   │                            │
    │<────────────────────────────│                            │
    │  3. Returns presigned PUT   │                            │
    │     URL + storage_key       │                            │
    │                             │                            │
    │  4. PUT file directly ──────────────────────────────────>│
    │<──────────────────────────────────────────────────────── │
    │                             │                            │
    │  5. POST /complete          │                            │
    │     (storage_key, sha, ...) │                            │
    │────────────────────────────>│  6. head_object() ────────>│
    │                             │<────────────────────────── │
    │                             │  7. Validate metadata       │
    │                             │  8. Create CourseMaterial   │
    │<────────────────────────────│                            │
    │  9. CourseMaterial created  │                            │
```

## Storage Key Format

```
tenants/{tenant_id}/courses/{course_id}/materials/{sha256[:16]}/{filename}
```

The SHA-256 prefix ensures idempotency — re-uploading the same file
produces the same key, preventing duplicate objects.

## Security

### Storage Key Validation
- `validate_storage_key_tenant_course()` ensures the key belongs to the
  current tenant and course
- Cross-tenant key injection returns 400 Bad Request
- Path traversal (`../`, absolute paths) is blocked by `_sanitize_filename()`

### Upload URL Endpoint
- Admin only (`get_current_admin`)
- Validates MIME type (PDF, Office docs, text)
- Validates file size (100 MB max)
- Validates SHA-256 format (64-char hex)
- Checks for duplicate SHA before issuing URL

### Complete Endpoint
- Admin only
- Validates storage key prefix (tenant + course)
- Verifies object exists via `head_object()`
- Validates content length matches declared size
- Checks for duplicate SHA-256
- Creates CourseMaterial record only after all validations pass

### Download
- Requires enrollment (CONFIRMADA or CONCLUIDA) or admin role
- Returns presigned GET URL (expires in `STORAGE_WATCH_URL_EXPIRATION`)
- Bucket must be private — no anonymous access

## Configuration

### Required Environment Variables (Production)

| Variable | Description | Example |
|----------|-------------|---------|
| `STORAGE_BACKEND` | Storage backend type | `s3` |
| `STORAGE_ENDPOINT` | S3-compatible endpoint URL | `https://s3.example.com` |
| `STORAGE_ACCESS_KEY` | Access key | (secret) |
| `STORAGE_SECRET_KEY` | Secret key | (secret) |
| `STORAGE_BUCKET` | Bucket name | `wr-cursos-materials` |
| `STORAGE_REGION` | Region | `auto` or `us-east-1` |
| `STORAGE_WATCH_URL_EXPIRATION` | Presigned URL TTL (seconds) | `7200` |

### Local Development

Set `STORAGE_BACKEND=local` to use the local filesystem. Files are
stored in `api/.local_storage/` and served via the `/api/v1/storage/`
endpoints.

## API Endpoints

### POST /api/v1/courses/{course_id}/materials/upload-url
**Admin only.** Request a presigned PUT URL.

Request body:
```json
{
  "filename": "apostila-nr10.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 1048576,
  "sha256": "a1b2c3d4..."
}
```

Response:
```json
{
  "upload_url": "https://s3.example.com/bucket/...",
  "storage_key": "tenants/{tid}/courses/{cid}/materials/a1b2c3d4.../apostila-nr10.pdf",
  "expires_in": 3600
}
```

### POST /api/v1/courses/{course_id}/materials/complete
**Admin only.** Finalize upload after successful PUT.

Request body:
```json
{
  "storage_key": "tenants/{tid}/courses/{cid}/materials/a1b2c3d4.../apostila-nr10.pdf",
  "title": "Apostila NR-10",
  "mime_type": "application/pdf",
  "size_bytes": 1048576,
  "sha256": "a1b2c3d4...",
  "document_type": "APOSTILA"
}
```

Response: `CourseMaterialResponse` (201 Created)

### GET /api/v1/courses/{course_id}/materials
**Enrolled students or admin.** List active materials.

### GET /api/v1/courses/{course_id}/materials/{material_id}/download
**Enrolled students or admin.** Get presigned download URL.

### DELETE /api/v1/courses/{course_id}/materials/{material_id}
**Admin only.** Soft-delete (sets `is_active=false`).

## Batch Uploader

The script `api/app/scripts/upload_wr_course_materials.py` uploads the
47 WR apostilas via the API (no direct DB access required).

### Authentication

Set one of:
- `WR_ADMIN_EMAIL` + `WR_ADMIN_PASSWORD` (script logs in via API)
- `WR_ADMIN_TOKEN` (pre-existing JWT)

### Usage

```bash
# Dry run (validate SHA, check existing, no uploads)
python -m app.scripts.upload_wr_course_materials --dry-run \
  --api-url https://wr-api-production.up.railway.app

# Real upload
python -m app.scripts.upload_wr_course_materials --apply \
  --api-url https://wr-api-production.up.railway.app
```

### Idempotency

Running the script a second time produces:
- 47 SKIP_DUPLICATE (materials already exist)
- 0 uploads

The SHA-256 prefix in storage keys prevents duplicate objects. The
duplicate SHA check in the API prevents duplicate CourseMaterial records.

## Document Types

| Type | Description |
|------|-------------|
| `APOSTILA` | Course textbook/handout |
| `MATERIAL_COMPLEMENTAR` | Supplementary material |
| `MANUAL` | Technical manual |
| `REFERENCIA` | Reference document |
| `OUTRO` | Other |

## What Materials Do NOT Affect

- Lesson progress (materials are separate from lessons)
- Course completion
- Certificate issuance

## Production Status (2026-08-26)

### Pipeline Implementation: COMPLETE

- PR #24 merged to main (`a7c81fe`)
- Backend deployed to Railway (healthy)
- Frontend deployed to Vercel (READY)
- All tests passing (783 backend, 387 frontend)
- 47 PDFs validated locally (47 SHA_MATCH, 0 MISMATCH)

### Production Upload: BLOCKED

**OWNER_ACTION_REQUIRED**: S3 storage credentials are not configured in
Railway. The following environment variables must be set:

```
STORAGE_BACKEND=s3
STORAGE_ENDPOINT=<endpoint>
STORAGE_ACCESS_KEY=<access-key>
STORAGE_SECRET_KEY=<secret-key>
STORAGE_BUCKET=<private-bucket>
STORAGE_REGION=<region>
STORAGE_WATCH_URL_EXPIRATION=7200
```

Once configured, run:

```bash
# 1. Generate pg_dump backup
# 2. Validate bucket is private
# 3. Dry run
python -m app.scripts.upload_wr_course_materials --dry-run \
  --api-url https://wr-api-production.up.railway.app

# 4. Apply
python -m app.scripts.upload_wr_course_materials --apply \
  --api-url https://wr-api-production.up.railway.app
```
- Enrollment status

Materials are purely downloadable resources for enrolled students.
