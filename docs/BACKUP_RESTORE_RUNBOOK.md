# Backup & Restore Runbook

## Databases

### LMS PostgreSQL (Plataforma de Cursos)

- **Provider:** Railway (Postgres volume)
- **Service name:** Postgres
- **Project:** wr-white-label-ceo-demo
- **Connection:** `railway connect Postgres` (via SSH tunnel)

### Central WR PostgreSQL

- **Provider:** Railway (Postgres volume)
- **Service name:** Postgres
- **Project:** central-wr-backend
- **Connection:** `railway connect Postgres` (via SSH tunnel)

## Current Backup Status

Railway provides volume-based persistence but does **NOT** guarantee
automated backups on the free/hobby tier. The following must be
configured before commercial launch:

## Recommended Backup Strategy

### RPO (Recovery Point Objective)

- **Target:** 24 hours (daily backups)
- **Maximum acceptable data loss:** 1 day of transactions

### RTO (Recovery Time Objective)

- **Target:** 4 hours
- **Maximum acceptable downtime:** 4 hours from incident to restoration

### Retention Policy

- **Daily backups:** 7 days
- **Weekly backups:** 4 weeks
- **Monthly backups:** 12 months

## Backup Options (choose one, requires owner authorization)

### Option A: Railway Pro plan

- Upgrade Railway project to Pro plan
- Enables automated daily backups with point-in-time recovery
- Cost: ~$20/month per project

### Option B: External pg_dump cron

- Set up a cron job on an external server that:
  1. Connects to the Railway Postgres via SSH tunnel
  2. Runs `pg_dump` with `--no-owner --no-privileges`
  3. Encrypts the dump with GPG
  4. Uploads to S3-compatible storage (Cloudflare R2, Backblaze B2)
- **Do NOT store unencrypted dumps in Git or public buckets**
- **Do NOT include PII in dump filenames**

### Option C: Managed PostgreSQL (external)

- Migrate to a managed PostgreSQL provider (Supabase, Neon, RDS)
- Built-in automated backups and PITR
- Higher cost but fully managed

## Restore Procedure (disposable environment test)

### Pre-restore validation

1. Spin up a disposable Railway environment or local Docker Postgres
2. Copy the encrypted backup to the restore target
3. Decrypt: `gpg --decrypt backup.sql.gpg > backup.sql`

### Restore steps

```bash
# Connect to the target database
psql $DATABASE_URL < backup.sql

# Verify migrations
cd api && alembic current

# Verify critical tables
psql $DATABASE_URL -c "SELECT count(*) FROM tenants;"
psql $DATABASE_URL -c "SELECT count(*) FROM users;"
psql $DATABASE_URL -c "SELECT count(*) FROM courses;"
psql $DATABASE_URL -c "SELECT count(*) FROM enrollments;"
psql $DATABASE_URL -c "SELECT count(*) FROM certificates;"
psql $DATABASE_URL -c "SELECT count(*) FROM payments;"
```

### Post-restore validation

1. Run `pytest tests/ -q` against the restored database
2. Verify health endpoint: `curl /health/ready`
3. Verify tenant isolation: cross-tenant queries return empty
4. Verify audit logs are intact

### Production restore

> **WARNING:** Never restore directly to production without testing
> in a disposable environment first. Production restore requires
> explicit owner authorization.

1. Notify all users of planned downtime
2. Put the application in maintenance mode
3. Stop the backend service
4. Restore the database
5. Run `alembic upgrade head` to apply any pending migrations
6. Start the backend service
7. Verify health endpoints
8. Remove maintenance mode
9. Notify users of restored service

## Backup Verification Script

A read-only verification script is available at:
`api/app/scripts/verify_backup.py`

This script checks:
- DATABASE_URL is configured
- Postgres is accessible
- Current migration head matches expected
- Critical tables exist and have data
- No data is copied or exported
