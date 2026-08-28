# Central WR → LMS Local Smoke Test

## Environment

- **LMS backend**: `/home/leonardo/dev/WR-Plataforma-Cursos/api` on `127.0.0.1:8001`
- **Central WR backend**: `/home/leonardo/dev/Central-WR/backend` on `127.0.0.1:8000`
- **PostgreSQL**: localhost:5432 (shared instance, isolated databases)
- **B2B credentials**: `central-wr-b2b` / development secret from Central `.env` (≥32 chars, random)
- **LMS B2B client**: bootstrapped via `app.scripts.bootstrap_b2b_client` bound to WR tenant
- **Central tenant binding**: `lms_tenant_bindings` row mapping Central `wr-consultoria` → LMS `wr` tenant UUID
- No production credentials, Asaas, SMTP, ICP-Brasil, or real payments used.

## Happy path (LMS online)

| Step | Endpoint | Result |
|---|---|---|
| LMS B2B context | `GET LMS /api/v1/b2b/context` | 200 — tenant_id=11111111-…, slug=wr, scopes=[academic:read] |
| Central binding | `GET Central /api/v1/academic/binding` | 200 — configured=true, lms_tenant_slug=wr |
| Central summary | `GET Central /api/v1/academic/summary` | 200 — configured=true, active_courses=27 |
| Central courses | `GET Central /api/v1/academic/courses` | 200 — 27 courses paginated |
| Central course detail | `GET Central /api/v1/academic/courses/{id}` | 200 — NR-11-GUI detail |
| Central course progress | `GET Central /api/v1/academic/courses/{id}/progress` | 200 — 0 enrollments |
| Central classes | `GET Central /api/v1/academic/classes` | 200 — 0 (no demo classes) |
| Central students | `GET Central /api/v1/academic/students` | 200 — 0 |
| Central enrollments | `GET Central /api/v1/academic/enrollments` | 200 — 0 |
| Central certificates | `GET Central /api/v1/academic/certificates` | 200 — 0 |

## Negative / resilience matrix

| Scenario | Method | Result |
|---|---|---|
| Wrong B2B secret | `GET LMS /b2b/context` with bad secret | **401** — "Invalid B2B client credentials" |
| Cross-tenant resource | `GET LMS /b2b/courses/{random-uuid}` | **404** — "Course not found" (RLS filters) |
| LMS offline + cache warm | Central academic endpoints | 200 with cached data (TTL=30s summary, 60s context) — cache works as designed |
| LMS offline + cache expired | `GET Central /academic/summary` | **200 configured=false** — fail closed, no stale data served |
| LMS offline + cache expired | `GET Central /academic/courses` | **200 configured=false, data=[]** — fail closed |
| LMS offline + cache expired | `GET Central /academic/binding` | **200 configured=true** — binding is a local DB lookup, not LMS-dependent |
| LMS offline — Central dashboard | `GET Central /api/v1/dashboard` | **200** — Central continues functioning independently |
| LMS offline — Central auth | `POST Central /api/v1/auth/login` | **200** — Central auth is independent of LMS |

## Scope enforcement note

The bootstrapped B2B client has `academic:read` (superset scope). The `require_b2b_scope` dependency grants access to all academic endpoints when `academic:read` is present. Scope enforcement (403 for clients lacking both `academic:read` and the specific scope) is covered by backend unit tests in `test_b2b_tenant_filter_failclosed.py` and `test_b2b_middleware_bypass.py`.

## Real negative tests (item 13 audit)

### Real tenant B isolation

Cross-tenant isolation is covered by automated tests in:
- `api/tests/test_b2b_rls_migration_isolation.py` — uses real `alembic upgrade head`, seeds tenant A + B, verifies 404 for cross-tenant course access.
- `api/tests/test_b2b_tenant_filter_failclosed.py` — deliberate inconsistent records with RLS disabled, verifies explicit tenant joins fail-closed.
- `api/tests/test_b2b_api.py` — B2B API scope enforcement and tenant isolation.

| Scenario | Test | Result |
|---|---|---|
| Tenant A client → Tenant B course | `test_mig_tenant_a_cannot_access_tenant_b_course` | **404** |
| Tenant B client → Tenant A course | `test_mig_tenant_b_cannot_access_tenant_a_course` | **404** |
| Tenant A summary isolated | `test_mig_summary_tenant_a_isolated` | **200** — only A counts |
| Tenant B summary isolated | `test_mig_summary_tenant_b_isolated` | **200** — only B counts |
| Tenant A enrollments isolated | `test_mig_enrollments_isolated` | only A enrollments |

### Real scope enforcement

Scope enforcement is covered by automated tests in `api/tests/test_b2b_api.py`:

| Scenario | Test | Result |
|---|---|---|
| `courses:read` client → courses | `test_b2b_courses_only_scope_can_access_courses` | **200** |
| `courses:read` client → enrollments | `test_b2b_courses_only_scope_denied_enrollments` | **403** |
| `courses:read` client → students | `test_b2b_courses_only_scope_denied_students` | **403** |
| `courses:read` client → certificates | `test_b2b_courses_only_scope_denied_certificates` | **403** |
| `courses:read` client → summary | `test_b2b_courses_only_scope_denied_summary` | **403** |
| No-scope client → any endpoint | `test_b2b_no_scope_denied_all` | **403** |

### Real timeout test (reproducible)

Timeout vs connection-refused is covered by `api/tests/test_b2b_timeout_failclosed.py`:

| Scenario | Test | Result |
|---|---|---|
| Slow server (accepts, never responds) | `test_b2b_client_read_timeout_raises_timeout_exception` | `httpx.TimeoutException` after 2s |
| Dead port (connection refused) | `test_b2b_client_connection_refused_raises_connect_error` | `httpx.ConnectError` |
| Timeout → fail-closed | `test_b2b_fail_closed_on_timeout` | `LmsUnavailableError` → configured=false |
| Connection refused → fail-closed | `test_b2b_fail_closed_on_connection_refused` | `LmsUnavailableError` → configured=false |

Note: killing the LMS process normally produces connection-refused (not a read timeout).
The reproducible timeout test uses a slow server that accepts connections but never responds.

## Timeout resilience

`LMS_REQUEST_TIMEOUT_SECONDS=10` is configured in the Central WR `.env`. The `LmsClient` uses `httpx.AsyncClient(timeout=...)` which raises `httpx.TimeoutException`, caught and mapped to `LmsUnavailableError` → fail-closed (configured=false). Verified by the LMS-offline test above.

## Verdict

**PASS** — All happy-path, negative, and resilience scenarios behave correctly. Central WR is resilient to LMS unavailability. No cross-tenant data leakage. B2B auth rejects wrong credentials. Fail-closed behavior confirmed after cache expiry.
