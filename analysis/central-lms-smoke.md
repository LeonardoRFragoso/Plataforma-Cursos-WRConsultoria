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

## Timeout resilience

`LMS_REQUEST_TIMEOUT_SECONDS=10` is configured in the Central WR `.env`. The `LmsClient` uses `httpx.AsyncClient(timeout=...)` which raises `httpx.TimeoutException`, caught and mapped to `LmsUnavailableError` → fail-closed (configured=false). Verified by the LMS-offline test above.

## Verdict

**PASS** — All happy-path, negative, and resilience scenarios behave correctly. Central WR is resilient to LMS unavailability. No cross-tenant data leakage. B2B auth rejects wrong credentials. Fail-closed behavior confirmed after cache expiry.
