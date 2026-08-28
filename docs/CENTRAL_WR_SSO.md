# Central WR SSO — Plataforma de Cursos (LMS) Receiver

This document describes the Single Sign-On (SSO) integration where the
**Central WR** platform acts as the Identity Provider (IdP) and the
**Plataforma de Cursos (LMS)** acts as the Service Provider (SP / relying
party).

## Architecture

```
┌─────────────┐        ┌──────────────┐        ┌─────────────────┐
│  Browser    │        │ Central WR   │        │  LMS (this app) │
│  (user)     │        │  (IdP)       │        │  (SP)           │
└──────┬──────┘        └──────┬───────┘        └────────┬────────┘
       │                      │                         │
       │ 1. Click "Plataforma │                         │
       │    de Cursos"        │                         │
       │─────────────────────>│                         │
       │                      │                         │
       │ 2. Redirect to LMS   │                         │
       │    /sso/callback     │                         │
       │    ?code=...&state=..│                         │
       │<─────────────────────│                         │
       │                      │                         │
       │ 3. POST /api/v1/sso/exchange {code, state}     │
       │───────────────────────────────────────────────>│
       │                      │                         │
       │                      │ 4. POST /api/v1/sso/lms │
       │                      │    /exchange            │
       │                      │    {client_id,          │
       │                      │     client_secret,      │
       │                      │     code}               │
       │                      │<────────────────────────│
       │                      │                         │
       │                      │ 5. Identity claims      │
       │                      │    {sub, email, name,   │
       │                      │     role, tenant_id}    │
       │                      │────────────────────────>│
       │                      │                         │
       │                      │    6. Find/create user  │
       │                      │    7. Issue LMS JWT     │
       │                      │                         │
       │ 8. {access_token, refresh_token}               │
       │<───────────────────────────────────────────────│
       │                      │                         │
       │ 9. GET /api/v1/auth/me (with token)            │
       │───────────────────────────────────────────────>│
       │                      │                         │
       │ 10. Redirect to /dashboard                      │
       │                      │                         │
```

### Sequence Diagram (Mermaid)

```mermaid
sequenceDiagram
    participant U as Browser (User)
    participant C as Central WR (IdP)
    participant L as LMS (SP)

    U->>C: 1. Click "Plataforma de Cursos"
    C-->>U: 2. Redirect to /sso/callback?code=...&state=...
    U->>L: 3. POST /api/v1/sso/exchange {code, state}
    L->>C: 4. POST /api/v1/sso/lms/exchange {client_id, client_secret, code}
    C-->>L: 5. Identity claims {sub, email, name, role, tenant_id}
    L->>L: 6. Find or create user + ExternalIdentity link
    L->>L: 7. Issue LMS JWT (access + refresh)
    L-->>U: 8. {access_token, refresh_token}
    U->>L: 9. GET /api/v1/auth/me (Bearer token)
    L-->>U: 10. User profile
    U->>U: 11. Redirect to /dashboard
```

## Endpoints

### LMS (this app)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/sso/exchange` | Receives `{code, state, target_application}` from the frontend, exchanges the code server-to-server with Central WR, and returns `{access_token, refresh_token, token_type}`. |

### Central WR (IdP)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/sso/lms/start` | Initiates the SSO flow (called by the Central WR frontend). |
| `POST` | `/api/v1/sso/lms/exchange` | Exchanges an authorization code for identity claims. Called server-to-server by the LMS with `{client_id, client_secret, code, target_application}`. Returns `{sub, email, name, role, tenant_id, source}`. |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CENTRAL_WR_FRONTEND_URL` | `http://localhost:5173` | Central WR frontend URL (HTTPS required in production). |
| `CENTRAL_WR_BACKEND_URL` | `http://localhost:8000` | Central WR backend URL (HTTPS required in production). |
| `CENTRAL_WR_SSO_CLIENT_ID` | `lms-wr-cursos` | OAuth client ID identifying the LMS to Central WR. |
| `CENTRAL_WR_SSO_CLIENT_SECRET` | `change-me-sso-secret` | OAuth client secret. **Must be >= 32 chars in production.** |
| `CENTRAL_WR_TRUSTED_TENANT_ID` | (empty) | UUID of the Central WR tenant trusted for SSO. **Required in production.** |
| `VITE_CENTRAL_WR_URL` | `http://localhost:5173` | Frontend env var for the "Voltar à Central WR" sidebar link. |
| `CORS_ORIGINS` | — | Must include the Central WR frontend URL so the browser can call the LMS API. |

### CENTRAL_WR_TRUSTED_TENANT_ID — Defense in Depth

**This setting is OBRIGATÓRIO in production.** The config validator blocks
startup if it is empty or not a valid UUID when `ENVIRONMENT=production`.

It must contain the UUID of the WR tenant **in Central WR** — the tenant
that is authorized to send ADMIN users via SSO.

**CRITICAL: This is NOT the same as `WR_TENANT_ID`.**

- `WR_TENANT_ID` (in `app/core/constants.py`) is the LMS's **internal**
  tenant UUID — the tenant the LMS uses for its own multi-tenant isolation.
- `CENTRAL_WR_TRUSTED_TENANT_ID` is the **Central WR** tenant UUID — the
  tenant in the Central WR database that is authorized to use SSO for the
  LMS.

These are **independent identity namespaces**. The Central WR tenant UUID
and the LMS `WR_TENANT_ID` are not related and must not be confused. They
live in separate databases with separate tenant tables.

When the LMS receives identity claims from Central WR, it validates that
`claims["tenant_id"] == CENTRAL_WR_TRUSTED_TENANT_ID` **before** any user
lookup, provisioning, or token issuance. This prevents an ADMIN from a
different Central WR tenant (e.g. another company) from gaining SSO access
to the LMS — even if they share the same email as an existing LMS user.

In development/test, this setting may be left empty to allow local testing
without a real Central WR tenant UUID.

## Role Mapping

| Central WR Role | LMS Role | Behavior |
|-----------------|----------|----------|
| `ADMIN` | `admin` | Allowed — issues LMS tokens. |
| Any other | — | **Rejected with 403.** Only ADMIN SSO is allowed for now. |

The role is normalized to uppercase before mapping. The LMS `admin` role
grants access to the operations dashboard and management features.

## Account Linking & Provisioning

When the LMS receives identity claims from Central WR, it resolves the local
user in this order:

1. **ExternalIdentity lookup** — Find an `ExternalIdentity` row with
   `provider="central-wr"` and `external_subject=claims["sub"]`. If found,
   the linked user is used. This is the fast path for returning SSO users.

2. **Email match** — If no external identity exists, look up a `User` by
   normalized email within the WR tenant (`WR_TENANT_ID`). If found, an
   `ExternalIdentity` link is created so subsequent logins use the fast path.

3. **Auto-provisioning** — If no user is found by either method, a new
   `User` is created with:
   - `role = admin` (mapped from Central ADMIN)
   - `password_hash = None` (SSO-only — cannot log in with a password)
   - `is_active = True`
   - `tenant_id = WR_TENANT_ID`
   - An `ExternalIdentity` link is created simultaneously.

This ensures users are never duplicated and existing accounts are seamlessly
linked on first SSO login.

## ExternalIdentity Model

```
external_identities
├── id              (UUID, PK)
├── provider        (String(80), indexed)         — "central-wr"
├── external_subject (String(255), indexed)       — Central WR user ID
├── user_id         (UUID FK → users.id, CASCADE)
├── tenant_id       (UUID FK → tenants.id, CASCADE)
├── created_at      (DateTime)
└── last_login_at   (DateTime, updated on each SSO login)

Unique: (provider, external_subject)
RLS: ENABLE + FORCE, policy tenant_isolation_external_identities
```

## Security

- **Server-to-server exchange**: The authorization code is exchanged
  server-to-server (LMS backend → Central WR backend) using
  `httpx.AsyncClient`. The `client_secret` never reaches the browser.
- **No secrets in logs**: Structured log events (`sso_login_success`,
  `sso_account_linked`, `sso_account_provisioned`, `sso_login_failed`) never
  include tokens, codes, or secrets. Only non-sensitive identifiers
  (`user_id`, `provider`, `reason`) are logged.
- **Role enforcement**: Only Central WR `ADMIN` users are accepted. All other
  roles are rejected with 403 before any user lookup or token issuance.
- **RLS**: The `external_identities` table has Row Level Security enabled with
  a `tenant_id` isolation policy, matching all other tenant-scoped tables.
- **Tenant context**: The SSO callback operates within the WR/master tenant.
  The frontend sends `X-Tenant-Slug: wr` on the exchange request, which the
  tenant middleware resolves. The endpoint is exempt from subscription
  enforcement (`_ENFORCEMENT_EXEMPT_PREFIXES` includes `/api/v1/sso`).
- **Auto-provisioned users have no password**: They can only authenticate via
  SSO. A `password_hash=None` user cannot log in via the normal
  `/api/v1/auth/login` endpoint (it requires a valid password hash).

## Local Development

1. Ensure both the Central WR and LMS backends are running.
2. Set the SSO env vars in `.env` (see above).
3. The Central WR frontend initiates the flow by calling
   `POST /api/v1/sso/lms/start` and redirecting the browser to the LMS
   `/sso/callback?code=...&state=...`.
4. The LMS frontend callback view (`SsoCallback.vue`) posts the code to
   `/api/v1/sso/exchange`, stores the returned tokens, fetches the user
   profile, and redirects to `/dashboard`.

### Running Tests

**Backend:**
```bash
cd api
WR_TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos_test_cert" \
  venv/bin/python -m pytest tests/test_sso.py -q --no-cov
```

**Frontend:**
```bash
cd web
npx vitest run src/__tests__/views/SsoCallback.spec.js src/__tests__/stores/auth.spec.js
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 400 "Código inválido ou expirado" | The authorization code has expired or already been used. | Re-initiate the SSO flow from Central WR. |
| 403 "Apenas administradores podem acessar via SSO" | The Central WR user does not have the `ADMIN` role. | Grant the ADMIN role in Central WR, or use a different account. |
| 502 "Não foi possível conectar à Central WR" | The LMS backend cannot reach `CENTRAL_WR_BACKEND_URL`. | Check that the Central WR backend is running and the URL is correct. |
| 502 "Resposta inválida da Central WR" | Central WR returned a malformed response. | Check Central WR logs. |
| Frontend shows "Parâmetros de autenticação ausentes" | The `/sso/callback` URL is missing `code` or `state` query params. | Re-initiate the SSO flow from Central WR. |
| User not found / not linked | The `ExternalIdentity` link was not created. | Check that the `external_identities` table exists (run `alembic upgrade head`). |

## Logout Decision

SSO logout is **not** propagated back to Central WR. When a user clicks
"Sair" in the LMS sidebar, only the LMS session is cleared (tokens removed
from localStorage). The user remains logged in at Central WR. This is a
deliberate decision:

- The LMS is one of potentially many applications connected to Central WR.
- Logging out of the LMS should not log the user out of Central WR (and thus
  all other connected applications).
- A future "global logout" flow (RP-initiated logout / back-channel logout)
  can be added if cross-application session termination is required.

The "Voltar à Central WR" link in the sidebar (visible to admin/super_admin
roles) allows the user to navigate back to Central WR without logging out of
the LMS.
