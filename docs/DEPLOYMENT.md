# Deployment Guide

## Architecture Overview

```
                    ┌─────────────┐
                    │   Internet   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Reverse    │
                    │  Proxy/TLS  │  (nginx/Caddy/managed ingress)
                    └──┬──────┬───┘
                       │      │
              ┌────────▼┐  ┌──▼────────┐
              │  Web    │  │   API     │
              │  (nginx)│  │ (uvicorn) │
              │  :80    │  │  :8000    │
              └─────────┘  └──┬─────┬──┘
                               │     │
                    ┌──────────▼┐ ┌──▼──────┐
                    │ PostgreSQL │ │  Redis  │
                    │   :5432    │ │  :6379  │
                    │ (internal) │ │(internal)│
                    └────────────┘ └─────────┘
```

## Prerequisites

### Infrastructure

- Docker host (Linux, 2+ GB RAM)
- PostgreSQL 16 (managed or containerized)
- Redis 7 (managed or containerized)
- Reverse proxy with TLS termination (nginx, Caddy, or cloud LB)
- S3-compatible object storage (Cloudflare R2, Backblaze B2, MinIO, AWS S3)
- SMTP server for email

### Secrets (via environment variables or .env file)

See `.env.production.example` for the full list. Critical:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | JWT signing key, ≥ 32 chars, random |
| `TENANT_SECRET_ENCRYPTION_KEY` | AES-GCM key for tenant secrets, 32 bytes base64 |
| `DB_PASSWORD` | PostgreSQL password |
| `ALLOWED_HOSTS` | Comma-separated allowed Host headers |
| `CORS_ORIGINS` | Comma-separated allowed CORS origins |
| `FRONTEND_URL` | Public frontend URL |
| `TRUSTED_PROXY_CIDRS` | CIDR of reverse proxy (e.g. `10.0.0.0/8`) |

## Deployment Steps

### 1. Prepare environment

```bash
cp .env.production.example .env.production
# Edit .env.production with real values
```

### 2. Backup database (if upgrading existing deployment)

```bash
# See docs/BACKUP_RESTORE.md
pg_dump -Fc -f backup_$(date +%Y%m%d_%H%M%S).dump $DATABASE_URL
```

### 3. Run migrations

Migrations run as a one-shot container BEFORE starting the API:

```bash
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
```

**Never run migrations from multiple API replicas simultaneously.**

### 4. Start services

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 5. Verify health

```bash
# API liveness
curl -fsS http://localhost:8000/health/live

# API readiness (checks DB)
curl -fsS http://localhost:8000/health/ready

# Frontend
curl -fsS http://localhost/health
```

### 6. Legacy MP token migration (if upgrading from pre-SaaS)

Only if tenants have `mp_access_token` in `tenant.settings`:

```bash
# Dry run
docker compose -f docker-compose.prod.yml run --rm api \
  python -m app.scripts.migrate_mp_access_tokens --dry-run

# Real run
docker compose -f docker-compose.prod.yml run --rm api \
  python -m app.scripts.migrate_mp_access_tokens
```

See `docs/RELEASE_RUNBOOK.md` for details.

### 7. Post-deploy verification

- [ ] API `/health/live` returns 200
- [ ] API `/health/ready` returns 200
- [ ] Frontend `/health` returns 200
- [ ] Admin login works
- [ ] Student login works
- [ ] Course catalog loads
- [ ] Certificate validation works
- [ ] Custom domain resolves (if configured)

## Reverse Proxy Configuration

### nginx example

```nginx
upstream wr_api {
    server 127.0.0.1:8000;
}
upstream wr_web {
    server 127.0.0.1:80;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    client_max_body_size 100M;
    proxy_read_timeout 300s;

    location / {
        proxy_pass http://wr_api;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 443 ssl http2;
    server_name app.example.com *.platform.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://wr_web;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}
```

### Key requirements

- **Host header preserved**: TenantResolver uses Host to identify tenants
- **X-Forwarded-Proto**: API needs to know it's behind HTTPS
- **X-Forwarded-For**: Only trusted if `TRUSTED_PROXY_CIDRS` includes the proxy IP
- **Request size limits**: `client_max_body_size` for file uploads
- **Timeouts**: Long enough for upload/report generation

## Custom Domain Architecture

For `cursos.cliente.com.br` to work:

1. **Wildcard DNS**: `*.platform.example.com` → reverse proxy IP
2. **Tenant slug**: `cliente.platform.example.com` (automatic)
3. **Custom domain**: `cursos.cliente.com.br` → CNAME to reverse proxy
4. **TLS**: Wildcard cert for `*.platform.example.com` + per-domain cert or Let's Encrypt
5. **TXT verification**: Tenant verifies domain ownership via TXT record
6. **Host preservation**: Reverse proxy must forward the original Host header

The database lifecycle (verification, status) exists in the application.
The infrastructure (DNS, TLS, ingress) must be provisioned separately.

## Worker Strategy

Single uvicorn worker per container. The application uses async I/O
(asyncpg, httpx, redis) which handles concurrency within one process.

To scale: run multiple containers behind a load balancer, not multiple
workers in one process. This gives:
- Predictable DB connection counts (pool_size=5 per container)
- Independent failure domains
- Independent scaling of API instances
