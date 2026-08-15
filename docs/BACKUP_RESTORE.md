# Backup and Restore

## PostgreSQL Backup

### Manual backup (before deployments)

```bash
pg_dump -Fc -f backup_$(date +%Y%m%d_%H%M%S).dump "$DATABASE_URL"
```

- `-Fc`: custom format (compressed, supports parallel restore)
- File naming: `backup_YYYYMMDD_HHMMSS.dump`

### Automated backup (cron)

```bash
# /etc/cron.d/pg-backup
0 2 * * * pg_dump -Fc -f /backups/backup_$(date +\%Y\%m\%d).dump "$DATABASE_URL"
```

### Retention

- Daily backups: 7 days
- Weekly backups: 4 weeks
- Monthly backups: 12 months

Adjust based on storage capacity and compliance requirements.

### Backup verification

A backup is only valid if it can be restored. Periodically test:

```bash
# Create test database
createdb wr_cursos_restore_test

# Restore
pg_restore -d wr_cursos_restore_test -c backup_YYYYMMDD.dump

# Verify
psql -d wr_cursos_restore_test -c "SELECT count(*) FROM tenants;"
psql -d wr_cursos_restore_test -c "SELECT count(*) FROM users;"
psql -d wr_cursos_restore_test -c "SELECT count(*) FROM enrollments;"

# Cleanup
dropdb wr_cursos_restore_test
```

## PostgreSQL Restore

### Full restore (disaster recovery)

```bash
# 1. Stop API
docker compose -f docker-compose.prod.yml stop api

# 2. Drop and recreate database
dropdb wr_cursos
createdb wr_cursos

# 3. Restore from backup
pg_restore -d "$DATABASE_URL" -c backup_YYYYMMDD_HHMMSS.dump

# 4. Verify
psql -d "$DATABASE_URL" -c "SELECT count(*) FROM tenants;"

# 5. Start API
docker compose -f docker-compose.prod.yml start api
```

### Point-in-time recovery

If PostgreSQL WAL archiving is enabled:

```bash
# Using pg_basebackup + WAL replay
# Consult PostgreSQL documentation for PITR setup
```

## Object Storage Backup

Course materials (videos, documents) are stored in S3-compatible storage.

### R2/B2/S3 backup strategies

1. **Bucket replication**: Configure cross-region replication
2. **Versioning**: Enable bucket versioning for accidental deletion protection
3. **Lifecycle**: Transition old versions to cheaper storage classes

### Restore from object storage

- Restore bucket from replication target
- Or restore individual objects from versioning
- Update `STORAGE_BUCKET` if restoring to a different bucket

## Encryption Key Backup

**CRITICAL**: `TENANT_SECRET_ENCRYPTION_KEY` and `SECRET_KEY` are NOT
stored in the database. If lost:

- `TENANT_SECRET_ENCRYPTION_KEY`: All encrypted tenant secrets (MP tokens)
  become unrecoverable. Tenants must re-enter their MP credentials.
- `SECRET_KEY`: All JWT tokens become invalid. All users must re-login.
  Password hashes are NOT affected (bcrypt/argon2 hashes are not encrypted).

### Key management

- Store keys in a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- Never commit keys to the repository
- Never put keys in docker-compose files
- Document key rotation procedure (requires re-encrypting all tenant secrets)

## Restore Testing

A backup strategy is incomplete unless restore is tested.

### Monthly restore test

1. Restore backup to disposable test database
2. Run migrations: `alembic upgrade head`
3. Start API against test database
4. Verify:
   - Admin login works
   - Tenant data present
   - Course catalog loads
   - Certificate validation works
5. Destroy test database

### Quarterly full disaster recovery test

1. Simulate complete failure
2. Restore database from backup
3. Restore object storage from replication
4. Deploy application from images
5. Verify all critical flows
6. Document time-to-recovery
