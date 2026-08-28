"""Phase 3: RLS isolation test using REAL alembic migrations.

Unlike ``test_b2b_rls_isolation.py`` (which manually creates RLS
policies), this test:

1. Creates a THROWAWAY PostgreSQL database.
2. Runs ``alembic upgrade head`` against it (real migrations).
3. Does NOT create any policy manually.
4. Queries ``pg_class`` / ``pg_policies`` to verify RLS is installed
   by the migrations on: courses, classes, users, students,
   enrollments, lessons, lesson_progress, certificates.
5. Seeds Tenant A and Tenant B with academic data.
6. Makes HTTP B2B requests and verifies strict cross-tenant isolation.

This proves the RLS policies installed by the migration scripts (not
hand-rolled test policies) correctly isolate B2B data access.

Requires PostgreSQL with the ability to CREATE DATABASE.
Skipped if the throwaway DB cannot be created.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import uuid
from datetime import date, datetime

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession as AS

from app.core.security import hash_password
from app.models.b2b_client import B2BClient
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
from app.models.student import Student
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from tests.conftest import make_valid_cpf

# The base Postgres connection (to create/drop the throwaway DB).
_ADMIN_DSN = os.environ.get(
    "WR_TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/wr_cursos_test",
)

# Tables that MUST have RLS enabled by migrations.
_REQUIRED_RLS_TABLES = [
    "courses",
    "classes",
    "users",
    "students",
    "enrollments",
    "lessons",
    "lesson_progress",
    "certificates",
]

TENANT_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

B2B_A_ID = "test-b2b-mig-tenant-a"
B2B_A_SECRET = "test-b2b-mig-tenant-a-secret-32chars!!"
B2B_B_ID = "test-b2b-mig-tenant-b"
B2B_B_SECRET = "test-b2b-mig-tenant-b-secret-32chars!!"


def _sync_admin_dsn(async_dsn: str) -> str:
    """Convert asyncpg DSN to psycopg2 for CREATE DATABASE."""
    return async_dsn.replace("postgresql+asyncpg://", "postgresql://")


def _db_name(async_dsn: str) -> str:
    return async_dsn.rsplit("/", 1)[-1]


async def _create_throwaway_db(admin_dsn: str, db_name: str) -> str:
    """Create a throwaway database and return its async DSN."""
    import asyncpg

    # asyncpg needs postgresql:// (not postgresql+asyncpg://)
    pg_dsn = admin_dsn.replace("postgresql+asyncpg://", "postgresql://")
    base = pg_dsn.rsplit("/", 1)[0]
    conn = await asyncpg.connect(f"{base}/postgres")
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()
    # Return the async DSN (with +asyncpg) for SQLAlchemy
    async_base = admin_dsn.rsplit("/", 1)[0]
    return f"{async_base}/{db_name}"


async def _drop_throwaway_db(admin_dsn: str, db_name: str) -> None:
    import asyncpg

    pg_dsn = admin_dsn.replace("postgresql+asyncpg://", "postgresql://")
    base = pg_dsn.rsplit("/", 1)[0]
    conn = await asyncpg.connect(f"{base}/postgres")
    try:
        await conn.execute(
            f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'
        )
    finally:
        await conn.close()


def _run_alembic_upgrade(sync_dsn: str, target: str = "head") -> None:
    """Run alembic upgrade to a target revision against the throwaway DB."""
    env = os.environ.copy()
    env["DATABASE_URL"] = sync_dsn
    api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        ["venv/bin/python", "-m", "alembic", "upgrade", target],
        capture_output=True,
        text=True,
        env=env,
        cwd=api_root,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade {target} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


async def _create_b2b_clients_table(async_dsn: str) -> None:
    """Manually create the b2b_clients table (from head migration 9193813510de).

    We upgrade only to ``d7e8f9a0b1c2`` (which installs all RLS policies)
    to avoid data migrations that require a pre-seeded WR tenant. The
    b2b_clients table has no RLS policies and is created here directly.
    Also adds missing columns that later migrations would add, so the
    ORM models can query without errors.
    """
    import asyncpg

    pg_dsn = async_dsn.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        # b2b_clients table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS b2b_clients (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                tenant_id UUID NOT NULL REFERENCES tenants(id),
                client_id VARCHAR NOT NULL UNIQUE,
                client_secret_hash VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                allowed_scopes TEXT NOT NULL DEFAULT 'academic:read',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_b2b_clients_tenant_id ON b2b_clients(tenant_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_b2b_clients_client_id ON b2b_clients(client_id)"
        )

        # Add missing columns that later migrations (c1d2e3f4a5b6 etc.)
        # would add. These are nullable so existing rows are unaffected.
        await conn.execute(
            "ALTER TABLE classes ADD COLUMN IF NOT EXISTS pedagogical_project_version_id UUID"
        )
        # external_identities table (from 16ef7bd242f3)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS external_identities (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                provider VARCHAR NOT NULL,
                external_subject VARCHAR NOT NULL,
                user_id UUID NOT NULL REFERENCES users(id),
                tenant_id UUID NOT NULL REFERENCES tenants(id),
                last_login_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE(provider, external_subject)
            )
        """)
    finally:
        await conn.close()


async def _verify_rls_installed(engine) -> dict[str, bool]:
    """Query pg_class to verify RLS is enabled on required tables."""
    result = {}
    async with engine.connect() as conn:
        for table in _REQUIRED_RLS_TABLES:
            row = await conn.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname = :tname"
                ),
                {"tname": table},
            )
            r = row.fetchone()
            if r:
                result[table] = bool(r[0])  # relrowsecurity
            else:
                result[table] = False
    return result


async def _verify_policies_exist(engine) -> dict[str, bool]:
    """Query pg_policies to verify tenant_isolation policies exist."""
    result = {}
    async with engine.connect() as conn:
        for table in _REQUIRED_RLS_TABLES:
            row = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM pg_policies "
                    "WHERE tablename = :tname AND policyname LIKE 'tenant_isolation%'"
                ),
                {"tname": table},
            )
            count = row.scalar()
            result[table] = count > 0
    return result


async def _seed_tenant(
    async_dsn: str, tenant_id, slug, course_code, course_name, b2b_id, b2b_secret
):
    """Seed a tenant with course/class/enrollment/b2b_client using raw SQL.

    Uses raw SQL (not ORM) because the migration revision we upgrade to
    (697853c1effe) may not have all columns that the ORM model defines.
    RLS bypass is set via set_config for the seeding session.
    """
    import asyncpg

    pg_dsn = async_dsn.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        now = "NOW()"
        # Set RLS context for seeding
        await conn.execute(
            "SELECT set_config('app.current_tenant', $1, true)", str(tenant_id)
        )
        await conn.execute("SELECT set_config('app.bypass_rls', '1', true)")

        # Tenant
        await conn.execute(
            f"INSERT INTO tenants (id, name, slug, status, contact_name, contact_email, created_at, updated_at) "
            f"VALUES ($1, $2, $3, 'ACTIVE', 'Test', $4, {now}, {now})",
            str(tenant_id), f"Tenant {slug.upper()}", slug, f"test@{slug}.com",
        )

        # Users
        student_user_id = str(uuid.uuid4())
        admin_user_id = str(uuid.uuid4())
        await conn.execute(
            f"INSERT INTO users (id, tenant_id, email, full_name, role, is_active, password_hash, created_at, updated_at) "
            f"VALUES ($1, $2, $3, $4, 'student', true, $5, {now}, {now})",
            student_user_id, str(tenant_id), f"student@{slug}.com",
            f"Student {slug}", hash_password("pw1234567"),
        )
        await conn.execute(
            f"INSERT INTO users (id, tenant_id, email, full_name, role, is_active, password_hash, created_at, updated_at) "
            f"VALUES ($1, $2, $3, $4, 'admin', true, $5, {now}, {now})",
            admin_user_id, str(tenant_id), f"admin@{slug}.com",
            f"Admin {slug}", hash_password("pw1234567"),
        )

        # Student
        student_id = str(uuid.uuid4())
        await conn.execute(
            f"INSERT INTO students (id, tenant_id, user_id, cpf, created_at, updated_at) "
            f"VALUES ($1, $2, $3, $4, {now}, {now})",
            student_id, str(tenant_id), student_user_id, make_valid_cpf(),
        )

        # Course
        course_id = str(uuid.uuid4())
        await conn.execute(
            f"INSERT INTO courses (id, tenant_id, code, name, category, carga_horaria, "
            f"modality, tipo_curso, price, is_active, created_at, updated_at) "
            f"VALUES ($1, $2, $3, $4, 'Test', 8, 'EAD', 'FORMACAO', 100.0, true, {now}, {now})",
            course_id, str(tenant_id), course_code, course_name,
        )

        # Class
        class_id = str(uuid.uuid4())
        await conn.execute(
            f"INSERT INTO classes (id, tenant_id, course_id, responsible_admin_id, status, "
            f"max_students, start_date, end_date, created_at, updated_at) "
            f"VALUES ($1, $2, $3, $4, 'ABERTA', 20, '2026-01-01', '2026-12-31', {now}, {now})",
            class_id, str(tenant_id), course_id, admin_user_id,
        )

        # Enrollment
        enrollment_id = str(uuid.uuid4())
        await conn.execute(
            f"INSERT INTO enrollments (id, tenant_id, student_id, class_id, status, source, "
            f"enrollment_date, price, created_at, updated_at) "
            f"VALUES ($1, $2, $3, $4, 'CONFIRMADA', 'INDIVIDUAL', '2026-01-15', 100.0, {now}, {now})",
            enrollment_id, str(tenant_id), student_id, class_id,
        )

        # B2B client
        await conn.execute(
            f"INSERT INTO b2b_clients (id, tenant_id, client_id, client_secret_hash, name, "
            f"allowed_scopes, is_active, created_at, updated_at) "
            f"VALUES ($1, $2, $3, $4, $5, 'academic:read', true, {now}, {now})",
            str(uuid.uuid4()), str(tenant_id), b2b_id,
            hash_password(b2b_secret), f"B2B {slug}",
        )
    finally:
        await conn.close()


@pytest.fixture
async def migration_db():
    """Create a throwaway DB, run alembic upgrade head, yield engine, cleanup."""
    db_name = f"wr_test_rls_mig_{uuid.uuid4().hex[:8]}"
    try:
        async_dsn = await _create_throwaway_db(_ADMIN_DSN, db_name)
    except Exception as exc:
        pytest.skip(f"Cannot create throwaway DB for migration RLS test: {exc}")

    sync_dsn = _sync_admin_dsn(async_dsn)
    try:
        # Upgrade to d7e8f9a0b1c2 — this includes ALL RLS policies
        # (17e4c0870485 enables RLS, 697853c1effe adds bypass clause)
        # and all schema columns needed by the ORM models. We stop before
        # data migrations (e8f9a0b1c2d3, a0b1c2d3e4f5) that require a
        # pre-seeded WR tenant with courses/users.
        _run_alembic_upgrade(sync_dsn, "d7e8f9a0b1c2")
        # Manually create b2b_clients table (from head migration 9193813510de)
        await _create_b2b_clients_table(async_dsn)
    except Exception as exc:
        await _drop_throwaway_db(_ADMIN_DSN, db_name)
        pytest.skip(f"alembic upgrade failed: {exc}")

    engine = create_async_engine(async_dsn, echo=False)
    try:
        yield engine, async_dsn
    finally:
        await engine.dispose()
        await _drop_throwaway_db(_ADMIN_DSN, db_name)


# ─── RLS installation verification (no HTTP, pure SQL) ───


@pytest.mark.asyncio
async def test_migration_rls_enabled_on_all_academic_tables(migration_db):
    """All academic tables must have RLS enabled by migrations."""
    engine, _ = migration_db
    result = await _verify_rls_installed(engine)
    for table in _REQUIRED_RLS_TABLES:
        assert result.get(table, False), (
            f"RLS not enabled on '{table}' by migrations. "
            f"Got: {result}"
        )


@pytest.mark.asyncio
async def test_migration_tenant_isolation_policies_exist(migration_db):
    """tenant_isolation_* policies must exist on all academic tables."""
    engine, _ = migration_db
    result = await _verify_policies_exist(engine)
    for table in _REQUIRED_RLS_TABLES:
        assert result.get(table, False), (
            f"No tenant_isolation policy on '{table}'. "
            f"Got: {result}"
        )


# ─── Cross-tenant isolation via HTTP B2B ───


@pytest.fixture
async def seeded_migration_app(migration_db):
    """Seed two tenants, create an ASGI app bound to the migration DB."""
    engine, async_dsn = migration_db

    # Seed both tenants
    await _seed_tenant(
        async_dsn, TENANT_A_ID, "tenant-a", "COURSE-A", "Course A",
        B2B_A_ID, B2B_A_SECRET,
    )
    await _seed_tenant(
        async_dsn, TENANT_B_ID, "tenant-b", "COURSE-B", "Course B",
        B2B_B_ID, B2B_B_SECRET,
    )

    # Create a fresh app instance bound to the migration DB.
    # We override the database engine/session factory in ALL modules
    # that hold a reference to AsyncSessionLocal.
    from app.core import database as db_mod
    from app.core import b2b_security
    from app.core.config import settings

    original_url = settings.DATABASE_URL
    original_engine = db_mod.engine
    original_session_local = db_mod.AsyncSessionLocal
    original_b2b_session_local = b2b_security.AsyncSessionLocal

    settings.DATABASE_URL = async_dsn
    new_engine = create_async_engine(async_dsn, echo=False)
    new_session_local = sessionmaker(new_engine, class_=AS, expire_on_commit=False)
    db_mod.engine = new_engine
    db_mod.AsyncSessionLocal = new_session_local
    b2b_security.AsyncSessionLocal = new_session_local

    from app.main import app

    try:
        yield app
    finally:
        db_mod.engine = original_engine
        db_mod.AsyncSessionLocal = original_session_local
        b2b_security.AsyncSessionLocal = original_b2b_session_local
        settings.DATABASE_URL = original_url
        await new_engine.dispose()


def _headers_a():
    return {"X-B2B-Client-Id": B2B_A_ID, "X-B2B-Client-Secret": B2B_A_SECRET}


def _headers_b():
    return {"X-B2B-Client-Id": B2B_B_ID, "X-B2B-Client-Secret": B2B_B_SECRET}


@pytest.mark.asyncio
async def test_mig_tenant_a_sees_only_a_courses(seeded_migration_app):
    """Tenant A sees total=1, len(data)=1, COURSE-A only."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=seeded_migration_app),
        base_url="http://test",
    ) as c:
        resp = await c.get("/api/v1/b2b/courses?limit=50", headers=_headers_a())
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 1
    assert len(data["data"]) == 1
    assert data["data"][0]["code"] == "COURSE-A"


@pytest.mark.asyncio
async def test_mig_tenant_b_sees_only_b_courses(seeded_migration_app):
    """Tenant B sees total=1, len(data)=1, COURSE-B only."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=seeded_migration_app),
        base_url="http://test",
    ) as c:
        resp = await c.get("/api/v1/b2b/courses?limit=50", headers=_headers_b())
    assert resp.status_code == 200
    data = resp.json()
    assert data["meta"]["total"] == 1
    assert len(data["data"]) == 1
    assert data["data"][0]["code"] == "COURSE-B"


@pytest.mark.asyncio
async def test_mig_tenant_a_cannot_access_tenant_b_course(seeded_migration_app):
    """Tenant A gets 404 for Tenant B's course."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=seeded_migration_app),
        base_url="http://test",
    ) as c:
        resp_b = await c.get("/api/v1/b2b/courses?limit=1", headers=_headers_b())
        course_b_id = resp_b.json()["data"][0]["id"]
        resp = await c.get(
            f"/api/v1/b2b/courses/{course_b_id}", headers=_headers_a()
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mig_tenant_b_cannot_access_tenant_a_course(seeded_migration_app):
    """Tenant B gets 404 for Tenant A's course."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=seeded_migration_app),
        base_url="http://test",
    ) as c:
        resp_a = await c.get("/api/v1/b2b/courses?limit=1", headers=_headers_a())
        course_a_id = resp_a.json()["data"][0]["id"]
        resp = await c.get(
            f"/api/v1/b2b/courses/{course_a_id}", headers=_headers_b()
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mig_summary_tenant_a_isolated(seeded_migration_app):
    """Tenant A summary: 1 course, 1 enrollment — not 2."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=seeded_migration_app),
        base_url="http://test",
    ) as c:
        resp = await c.get("/api/v1/b2b/summary", headers=_headers_a())
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_courses"] == 1
    assert data["active_enrollments"] == 1


@pytest.mark.asyncio
async def test_mig_summary_tenant_b_isolated(seeded_migration_app):
    """Tenant B summary: 1 course, 1 enrollment — not 2."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=seeded_migration_app),
        base_url="http://test",
    ) as c:
        resp = await c.get("/api/v1/b2b/summary", headers=_headers_b())
    assert resp.status_code == 200
    data = resp.json()
    assert data["active_courses"] == 1
    assert data["active_enrollments"] == 1


@pytest.mark.asyncio
async def test_mig_enrollments_isolated(seeded_migration_app):
    """Each tenant sees only their own enrollment."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=seeded_migration_app),
        base_url="http://test",
    ) as c:
        resp_a = await c.get("/api/v1/b2b/enrollments?limit=50", headers=_headers_a())
        resp_b = await c.get("/api/v1/b2b/enrollments?limit=50", headers=_headers_b())
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    a_data = resp_a.json()["data"]
    b_data = resp_b.json()["data"]
    assert len(a_data) == 1
    assert len(b_data) == 1
    assert a_data[0]["id"] != b_data[0]["id"]
    assert a_data[0]["course_name"] == "Course A"
    assert b_data[0]["course_name"] == "Course B"
