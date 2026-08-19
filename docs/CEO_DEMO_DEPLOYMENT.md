# CEO Demo — White Label Deployment Guide

This guide describes how to deploy the White Label CEO demo with two
tenants (WR + Alfa) on Railway (backend) + Vercel (frontend).

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Vercel (Frontend SPA)                                  │
│  ├── wr-cursos.vercel.app     → VITE_TENANT_SLUG=wr     │
│  └── alfa-academy.vercel.app  → VITE_TENANT_SLAG=alfa   │
└───────────────┬─────────────────────────────────────────┘
                │ X-Tenant-Slug header
                ▼
┌─────────────────────────────────────────────────────────┐
│  Railway (FastAPI Backend)                              │
│  ├── TRUSTED_FRONTEND_ORIGINS=vercel.app                │
│  ├── DEMO_SEED_MODE=true                                │
│  ├── MERCADO_PAGO_MOCK_MODE=true                        │
│  └── ENVIRONMENT=staging                                │
└───────────────┬─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│  Railway (PostgreSQL)                                   │
│  RLS enabled, tenant_id isolation                       │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- Railway account with PostgreSQL provisioned
- Vercel account
- Git repository connected to both platforms

## Backend (Railway)

### Environment Variables

```env
ENVIRONMENT=staging
DATABASE_URL=postgresql://...
SECRET_KEY=<generate-strong-secret>
TRUSTED_FRONTEND_ORIGINS=https://wr-cursos.vercel.app,https://alfa-academy.vercel.app
DEMO_SEED_MODE=true
MERCADO_PAGO_MOCK_MODE=true
DEMO_WR_ADMIN_EMAIL=admin@wr.demo
DEMO_WR_ADMIN_PASSWORD=<set-strong-password>
DEMO_ALFA_ADMIN_EMAIL=admin@alfa.demo
DEMO_ALFA_ADMIN_PASSWORD=<set-strong-password>
DEMO_WR_STUDENT_PASSWORD=<set-strong-password>
DEMO_ALFA_STUDENT_PASSWORD=<set-strong-password>
```

### Deploy Steps

1. Connect the `api/` directory to Railway
2. Railway auto-detects the Dockerfile and uses `PORT` env var
3. After first deploy, run the seed script:

```bash
# Via Railway shell or locally with DATABASE_URL set
DEMO_SEED_MODE=true \
DEMO_WR_ADMIN_EMAIL=admin@wr.demo \
DEMO_WR_ADMIN_PASSWORD=... \
DEMO_ALFA_ADMIN_EMAIL=admin@alfa.demo \
DEMO_ALFA_ADMIN_PASSWORD=... \
python -m app.scripts.seed_white_label_demo
```

The seed is idempotent — safe to re-run.

## Frontend (Vercel)

### Project 1: WR Tenant

1. Import the `web/` directory into Vercel
2. Set environment variables:
   ```env
   VITE_API_URL=https://<railway-backend>.up.railway.app
   VITE_TENANT_SLUG=wr
   ```
3. Deploy → get `wr-cursos.vercel.app`

### Project 2: Alfa Tenant

1. Import the same `web/` directory (new Vercel project)
2. Set environment variables:
   ```env
   VITE_API_URL=https://<railway-backend>.up.railway.app
   VITE_TENANT_SLUG=alfa
   ```
3. Deploy → get `alfa-academy.vercel.app`

### Custom Domains (Optional)

Assign custom domains in Vercel project settings:
- WR: `cursos.wrconsultoria.com.br`
- Alfa: `academy.alfa.com.br`

The backend resolves custom domains automatically when verified.

## Demo Flow

### 1. Branding Comparison
- Open `wr-cursos.vercel.app` → WR blue branding
- Open `alfa-academy.vercel.app` → Alfa orange branding
- Different logos, colors, favicons, tenant names

### 2. Data Isolation
- Login as WR admin → see only WR courses
- Login as Alfa admin → see only Alfa courses
- WR admin cannot access Alfa data (403)

### 3. White Label Settings
- Login as Alfa admin → `/settings/white-label`
- Change primary color → live re-branding
- Save → branding persists

### 4. Super Admin Panel
- Login as super_admin → `/super-admin`
- View all tenants, plans, subscriptions
- Approve partner leads → creates new tenant
- Suspend/activate subscriptions

### 5. Subscription Enforcement
- Super admin suspends Alfa subscription
- Alfa users get 503 on business operations
- Auth still works (can login)
- Super admin reactivates → Alfa works again

### 6. Demo Payment Simulator
- Student enrolls in course → pending payment
- Visit `/demo/payment/<payment_id>`
- Click "Approve" → enrollment confirmed
- Access course content

### 7. Certificate White Label
- Complete a course → download certificate
- WR certificate has WR blue + WR name
- Alfa certificate has Alfa orange + Alfa name

## Security Notes

- **DEMO_SEED_MODE** is gated: refuses to run in production
- **MERCADO_PAGO_MOCK_MODE** demo payment endpoints return 404 in production
- Demo credentials must be set via env vars, never hardcoded
- TRUSTED_FRONTEND_ORIGINS prevents spoofing of X-Tenant-Slug
- JWT tenant binding prevents cross-tenant token reuse
- RLS provides database-level isolation as defence in depth
