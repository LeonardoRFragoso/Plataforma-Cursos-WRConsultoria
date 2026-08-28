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
- Scope-restricted (currently `academic:read`)
- Independent from SSO secrets and JWT secrets

## Scopes

| Scope | Description |
|-------|-------------|
| `academic:read` | Read access to all academic data (courses, classes, students, enrollments, certificates, summary) |
| `courses:read` | Read access to courses (subset of academic:read) |
| `classes:read` | Read access to classes |
| `students:read` | Read access to students |
| `enrollments:read` | Read access to enrollments |
| `certificates:read` | Read access to certificates |

## Endpoints

All endpoints are under `/api/v1/b2b`.

### Summary

```
GET /api/v1/b2b/summary
```

Returns aggregated academic KPIs for the dashboard.

### Courses

```
GET /api/v1/b2b/courses?skip=0&limit=50&search=NR&is_active=true
GET /api/v1/b2b/courses/{course_id}
GET /api/v1/b2b/courses/{course_id}/progress
```

### Classes

```
GET /api/v1/b2b/classes?skip=0&limit=50&status_filter=ABERTA&course_id=...
GET /api/v1/b2b/classes/{class_id}
```

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

### Certificates

```
GET /api/v1/b2b/certificates?skip=0&limit=50&status_filter=ACTIVE&student_id=...
```

## LGPD

B2B responses are LGPD-safe:
- No CPF in any response
- No password_hash
- No JWT tokens
- No sensitive personal data beyond name and email (where necessary)

## Tenant Isolation

All B2B queries are scoped to the client's registered tenant. A B2B
client registered for tenant A cannot access tenant B's data — RLS
enforces this at the database level.

## Environment Variables

### LMS (Plataforma)

```
B2B_CENTRAL_WR_CLIENT_ID=central-wr-b2b
B2B_CENTRAL_WR_CLIENT_SECRET=<generated-secret>
B2B_CENTRAL_WR_TENANT_SLUG=wr
```

### Central WR

```
LMS_API_URL=http://localhost:8001
LMS_B2B_CLIENT_ID=central-wr-b2b
LMS_B2B_CLIENT_SECRET=<same-secret-as-lms>
LMS_REQUEST_TIMEOUT_SECONDS=10
```

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
| Secret | `CENTRAL_WR_SSO_CLIENT_SECRET` | `B2B_CENTRAL_WR_CLIENT_SECRET` (separate) |
| Flow | Browser redirect | Server-to-server HTTP |
| Data | User session | Academic data (read-only) |
