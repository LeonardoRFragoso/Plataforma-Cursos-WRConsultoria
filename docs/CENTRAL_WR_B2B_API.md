# Central WR B2B Read-Only API

## Overview

The LMS (Plataforma de Cursos) exposes a B2B read-only API that allows
the Central WR backend to query academic data without duplicating it.

This is a **separate** integration from SSO:

```
SSO flow (user-facing):
  Central Browser → SSO redirect → LMS Browser Session

B2B flow (backend-to-backend):
  Central Backend → B2B API → LMS Backend → LMS Database
```

## Authentication

B2B clients authenticate via HTTP headers:

```
X-B2B-Client-Id: <client_id>
X-B2B-Client-Secret: <client_secret>
```

The secret is stored as an argon2 hash in the `b2b_clients` table.
Each client is:
- Tenant-scoped (bound to one LMS tenant)
- Scope-restricted (e.g. `academic:read`, `courses:read`)
- Independent from SSO secrets and JWT secrets

### Missing/Invalid Credentials

All authentication failures return **401 Unauthorized** with the same
error message: `"Invalid B2B client credentials"`. This includes:
- Missing `X-B2B-Client-Id` header
- Missing `X-B2B-Client-Secret` header
- Non-existent client_id
- Wrong secret
- Inactive client

The uniform error message prevents leaking whether a client_id exists.

## Scopes

| Scope | Description |
|-------|-------------|
| `academic:read` | Superset — read access to ALL academic data (courses, classes, students, enrollments, certificates, summary, context) |
| `courses:read` | Read access to courses only |
| `classes:read` | Read access to classes only |
| `students:read` | Read access to students only |
| `enrollments:read` | Read access to enrollments only |
| `certificates:read` | Read access to certificates only |

`academic:read` is a **superset** scope: if a client has it, all
academic endpoints are accessible regardless of specific scopes.
Without any scope, all endpoints return **403 Forbidden**.

## RLS and Tenant Isolation

### How RLS Works with B2B

1. **Client lookup** (`b2b_clients` table): Uses a **privileged session**
   with `SET LOCAL app.bypass_rls = '1'`. The `b2b_clients` table does
   NOT have RLS enabled because we need to look up the client by
   `client_id` before knowing the tenant. See
   [§ b2b_clients RLS exemption](#b2b_clients-rls-exemption) below.

2. **Route session**: After authentication, a **new session** is created
   with `SELECT set_config('app.current_tenant', :tenant_id, true)`
   using a **parameterized query** (no string interpolation). This
   ensures RLS policies filter all queries to the client's tenant.

3. **ContextVar**: `current_tenant_id` is also set to keep the
   application-level context consistent.

### b2b_clients RLS Exemption

The `b2b_clients` table deliberately does NOT have RLS enabled. This is
acceptable because:
- It contains only client metadata (client_id, hashed secret, scopes)
- The secret is stored as an argon2 hash (never plaintext)
- Access occurs exclusively backend-to-backend (no public exposure)
- `tenant_id` is obtained only after authentication succeeds
- Enabling RLS would make client lookup impossible (chicken-and-egg)

### PostgreSQL set_config vs SET LOCAL

The B2B security module uses `SELECT set_config('app.current_tenant',
:tid, true)` with a parameterized query instead of `SET LOCAL
app.current_tenant = '...'` with string interpolation. This prevents
SQL injection and is the recommended approach for dynamic tenant
context.

## Endpoints

All endpoints are under `/api/v1/b2b`.

### Context

```
GET /api/v1/b2b/context
```

Returns the authenticated B2B client's context (no secret). Used by
Central WR to verify that the LMS tenant binding matches the
credential's actual tenant.

```json
{
  "tenant_id": "...",
  "tenant_slug": "wr",
  "client_id": "central-wr-b2b",
  "scopes": ["academic:read"]
}
```

### Summary

```
GET /api/v1/b2b/summary
```

Returns aggregated academic KPIs for the dashboard. The
`avg_progress_percent` field is the **mean of per-enrollment progress
percentages**, not a global completed/total ratio. This ensures the
value is always in [0, 100].

### Courses

```
GET /api/v1/b2b/courses?skip=0&limit=50&search=NR&is_active=true
GET /api/v1/b2b/courses/{course_id}
GET /api/v1/b2b/courses/{course_id}/progress
```

Course listings use **batch aggregation** (subqueries) for
`classes_count` and `students_count` — no N+1 queries.

### Classes

```
GET /api/v1/b2b/classes?skip=0&limit=50&status_filter=ABERTA&course_id=...
GET /api/v1/b2b/classes/{class_id}
```

Class listings use **batch aggregation** for `enrollments_count` and
`company_name` — no N+1 queries.

### Students

```
GET /api/v1/b2b/students?skip=0&limit=50&search=João&company=WR
GET /api/v1/b2b/students/{student_id}
```

### Enrollments

```
GET /api/v1/b2b/enrollments?skip=0&limit=50&status_filter=CONFIRMADA&course_id=...
GET /api/v1/b2b/enrollments/{enrollment_id}
```

Each enrollment includes `progress_percent` computed as
`completed_lessons / total_lessons * 100` (clamped to [0, 100]).

### Certificates

```
GET /api/v1/b2b/certificates?skip=0&limit=50&status_filter=ACTIVE&student_id=...
```

## avg_progress_percent Formula

The `avg_progress_percent` in the summary and course progress endpoints
is computed as:

1. For each active enrollment (PENDENTE or CONFIRMADA):
   - `progress = completed_lessons / total_lessons * 100`
   - If the course has no lessons, `progress = 0`
   - Progress is clamped to [0, 100]
2. The average of all per-enrollment progress values is returned.

This prevents the bug where `completed_lessons / total_lessons` could
exceed 100% when multiple students complete lessons across different
courses (the numerator was a global count, not per-enrollment).

## LGPD

B2B responses are LGPD-safe:
- No CPF in any response
- No password_hash
- No JWT tokens
- No client_secret_hash
- No refresh_token or access_token
- No sensitive personal data beyond name and email (where necessary)

The `X-B2B-Client-Secret` header is never logged.

## Tenant Isolation

All B2B queries are scoped to the client's registered tenant via RLS
(Row Level Security) at the PostgreSQL level. A B2B client registered
for tenant A cannot access tenant B's data.

Cross-tenant isolation is verified by integration tests
(`tests/test_b2b_rls_isolation.py`) that:
- Create two tenants with academic data
- Enable RLS on all academic tables
- Verify each B2B client only sees its own tenant's data
- Verify cross-tenant access returns 404

## Environment Variables

### LMS (Plataforma)

```
B2B_CENTRAL_WR_CLIENT_ID=central-wr-b2b
B2B_CENTRAL_WR_CLIENT_SECRET=<generated-secret>
B2B_CENTRAL_WR_TENANT_SLUG=wr
```

### Central WR

```
LMS_BACKEND_URL=http://localhost:8001
LMS_B2B_CLIENT_ID=central-wr-b2b
LMS_B2B_CLIENT_SECRET=<same-secret-as-lms>
LMS_REQUEST_TIMEOUT_SECONDS=10
```

## Multi-Tenant Scope (Phase 5)

**Current state**: Central WR has ONE B2B credential per deployment
(`LMS_B2B_CLIENT_ID` / `LMS_B2B_CLIENT_SECRET` in env). This credential
is bound to ONE LMS tenant (WR).

The `LmsTenantBinding` model in Central WR maps a Central tenant to an
LMS tenant. The Central backend verifies that the B2B context's
`tenant_id` matches the binding's `lms_tenant_id` before serving data.
If they don't match, the integration returns a configuration error.

**Future evolution** (not implemented in Phase 5):
- Per-binding credentials (credential vault)
- Service account per tenant
- Identity broker for multi-tenant SaaS

## Bootstrap

```bash
cd api
B2B_CENTRAL_WR_CLIENT_ID=central-wr-b2b \
B2B_CENTRAL_WR_CLIENT_SECRET=<secret> \
B2B_CENTRAL_WR_TENANT_SLUG=wr \
  venv/bin/python -m app.scripts.bootstrap_b2b_client
```

In development, re-running the script updates the secret if the client
already exists. In production, existing clients are never modified.

## Difference from SSO

| Aspect | SSO | B2B API |
|--------|-----|---------|
| Purpose | User login (Central → LMS) | Data query (Central backend → LMS backend) |
| Auth | Authorization code + client secret | Client ID + client secret (headers) |
| Secret | `LMS_SSO_CLIENT_SECRET` | `LMS_B2B_CLIENT_SECRET` (separate) |
| Flow | Browser redirect | Server-to-server HTTP |
| Data | User session | Academic data (read-only) |
| Missing auth | 401 | 401 (not 422) |
