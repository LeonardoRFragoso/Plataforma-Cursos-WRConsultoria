"""Phase 4: Concurrent multi-tenant stress test.

Verifies that under concurrent load (asyncio.gather with many
simultaneous requests from two B2B clients):
- ContextVar does not leak between requests
- RLS does not leak between tenants
- Responses never mix tenant data
- Tenant A never receives Tenant B's IDs or names

Uses the same RLS-enabled test setup as test_b2b_rls_isolation.py.
"""

import asyncio
import uuid
from datetime import date, datetime

import httpx
import pytest
from sqlalchemy import text

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.models.b2b_client import B2BClient
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
from app.models.student import Student
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole
from tests.conftest import make_valid_cpf

TENANT_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

B2B_A_ID = "test-b2b-conc-a"
B2B_A_SECRET = "test-b2b-conc-a-secret-32chars-pad!!"
B2B_B_ID = "test-b2b-conc-b"
B2B_B_SECRET = "test-b2b-conc-b-secret-32chars-pad!!"

_RLS_TABLES = [
    "courses", "classes", "students", "enrollments",
    "lessons", "lesson_progress", "certificates",
]


async def _enable_rls():
    async with engine.begin() as conn:
        for table in _RLS_TABLES:
            await conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
            await conn.execute(text(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}"))
            await conn.execute(text(
                f"CREATE POLICY tenant_isolation_{table} ON {table} "
                f"FOR ALL TO public "
                f"USING (current_setting('app.bypass_rls', true) = '1' "
                f"OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
                f"WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
                f"OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
            ))


async def _disable_rls():
    async with engine.begin() as conn:
        for table in _RLS_TABLES:
            await conn.execute(text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
            await conn.execute(text(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}"))


async def _seed_tenant(tenant_id, slug, course_code, course_name, b2b_id, b2b_secret):
    async with AsyncSessionLocal() as session:
        session.info["tenant_id"] = tenant_id
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        await session.execute(text("SET LOCAL app.bypass_rls = '1'"))

        session.add(Tenant(
            id=tenant_id, name=f"Tenant {slug.upper()}", slug=slug,
            status=TenantStatus.ACTIVE, contact_name="Test", contact_email=f"test@{slug}.com",
        ))
        await session.flush()

        student_user = User(
            tenant_id=tenant_id, email=f"student@{slug}.com",
            full_name=f"Student {slug}", password_hash=hash_password("pw1234567"),
            role=UserRole.STUDENT.value, is_active=True,
        )
        admin_user = User(
            tenant_id=tenant_id, email=f"admin@{slug}.com",
            full_name=f"Admin {slug}", password_hash=hash_password("pw1234567"),
            role=UserRole.ADMIN.value, is_active=True,
        )
        session.add_all([student_user, admin_user])
        await session.flush()

        student = Student(tenant_id=tenant_id, user_id=student_user.id, cpf=make_valid_cpf())
        session.add(student)
        await session.flush()

        course = Course(
            tenant_id=tenant_id, code=course_code, name=course_name,
            category="Test", carga_horaria=8, modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO, price=100.0, is_active=True,
        )
        session.add(course)
        await session.flush()

        cls = Class(
            tenant_id=tenant_id, course_id=course.id, responsible_admin_id=admin_user.id,
            status=ClassStatus.ABERTA,
            max_students=20, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        session.add(cls)
        await session.flush()

        enrollment = Enrollment(
            tenant_id=tenant_id, student_id=student.id, class_id=cls.id,
            status=EnrollmentStatus.CONFIRMADA, source=EnrollmentSource.INDIVIDUAL,
            enrollment_date=datetime(2026, 1, 15), price=100.0,
        )
        session.add(enrollment)

        session.add(B2BClient(
            tenant_id=tenant_id, client_id=b2b_id,
            client_secret_hash=hash_password(b2b_secret),
            name=f"B2B {slug}", allowed_scopes="academic:read", is_active=True,
        ))
        await session.commit()


@pytest.fixture(autouse=True)
async def conc_seed(setup_db):
    """Enable RLS and seed two tenants."""
    await _enable_rls()
    await _seed_tenant(TENANT_A_ID, "conc-a", "CONC-A", "Concurrent Course A", B2B_A_ID, B2B_A_SECRET)
    await _seed_tenant(TENANT_B_ID, "conc-b", "CONC-B", "Concurrent Course B", B2B_B_ID, B2B_B_SECRET)
    yield
    await _disable_rls()


def _headers_a():
    return {"X-B2B-Client-Id": B2B_A_ID, "X-B2B-Client-Secret": B2B_A_SECRET}


def _headers_b():
    return {"X-B2B-Client-Id": B2B_B_ID, "X-B2B-Client-Secret": B2B_B_SECRET}


# Number of concurrent iterations per tenant
N_ITERATIONS = 20


@pytest.mark.asyncio
async def test_concurrent_context_isolation(client: httpx.AsyncClient):
    """Concurrent /context requests — each tenant always gets its own ID."""
    async def fetch_a():
        resp = await client.get("/api/v1/b2b/context", headers=_headers_a())
        return resp.json()

    async def fetch_b():
        resp = await client.get("/api/v1/b2b/context", headers=_headers_b())
        return resp.json()

    tasks = []
    for _ in range(N_ITERATIONS):
        tasks.append(fetch_a())
        tasks.append(fetch_b())

    results = await asyncio.gather(*tasks)

    # Even indices are A, odd are B
    for i in range(0, len(results), 2):
        assert results[i]["tenant_id"] == str(TENANT_A_ID), f"Leak at index {i}"
        assert results[i]["tenant_slug"] == "conc-a"
    for i in range(1, len(results), 2):
        assert results[i]["tenant_id"] == str(TENANT_B_ID), f"Leak at index {i}"
        assert results[i]["tenant_slug"] == "conc-b"


@pytest.mark.asyncio
async def test_concurrent_courses_isolation(client: httpx.AsyncClient):
    """Concurrent /courses requests — each tenant only sees its own course."""
    async def fetch_a():
        resp = await client.get("/api/v1/b2b/courses?limit=50", headers=_headers_a())
        return resp.json()

    async def fetch_b():
        resp = await client.get("/api/v1/b2b/courses?limit=50", headers=_headers_b())
        return resp.json()

    tasks = []
    for _ in range(N_ITERATIONS):
        tasks.append(fetch_a())
        tasks.append(fetch_b())

    results = await asyncio.gather(*tasks)

    for i in range(0, len(results), 2):
        data = results[i]["data"]
        assert len(data) == 1
        assert data[0]["code"] == "CONC-A"
        assert data[0]["name"] == "Concurrent Course A"
    for i in range(1, len(results), 2):
        data = results[i]["data"]
        assert len(data) == 1
        assert data[0]["code"] == "CONC-B"
        assert data[0]["name"] == "Concurrent Course B"


@pytest.mark.asyncio
async def test_concurrent_summary_isolation(client: httpx.AsyncClient):
    """Concurrent /summary requests — each tenant sees only its own counts."""
    async def fetch_a():
        resp = await client.get("/api/v1/b2b/summary", headers=_headers_a())
        return resp.json()

    async def fetch_b():
        resp = await client.get("/api/v1/b2b/summary", headers=_headers_b())
        return resp.json()

    tasks = []
    for _ in range(N_ITERATIONS):
        tasks.append(fetch_a())
        tasks.append(fetch_b())

    results = await asyncio.gather(*tasks)

    for i in range(0, len(results), 2):
        assert results[i]["active_courses"] == 1
        assert results[i]["active_enrollments"] == 1
    for i in range(1, len(results), 2):
        assert results[i]["active_courses"] == 1
        assert results[i]["active_enrollments"] == 1


@pytest.mark.asyncio
async def test_concurrent_enrollments_isolation(client: httpx.AsyncClient):
    """Concurrent /enrollments requests — each tenant only sees its own."""
    async def fetch_a():
        resp = await client.get("/api/v1/b2b/enrollments?limit=50", headers=_headers_a())
        return resp.json()

    async def fetch_b():
        resp = await client.get("/api/v1/b2b/enrollments?limit=50", headers=_headers_b())
        return resp.json()

    tasks = []
    for _ in range(N_ITERATIONS):
        tasks.append(fetch_a())
        tasks.append(fetch_b())

    results = await asyncio.gather(*tasks)

    for i in range(0, len(results), 2):
        data = results[i]["data"]
        assert len(data) == 1
        assert data[0]["course_name"] == "Concurrent Course A"
    for i in range(1, len(results), 2):
        data = results[i]["data"]
        assert len(data) == 1
        assert data[0]["course_name"] == "Concurrent Course B"


@pytest.mark.asyncio
async def test_concurrent_mixed_endpoints_isolation(client: httpx.AsyncClient):
    """Mixed concurrent requests across endpoints — no tenant leakage."""
    async def fetch_a():
        results = {}
        r1 = await client.get("/api/v1/b2b/context", headers=_headers_a())
        r2 = await client.get("/api/v1/b2b/summary", headers=_headers_a())
        r3 = await client.get("/api/v1/b2b/courses?limit=50", headers=_headers_a())
        r4 = await client.get("/api/v1/b2b/enrollments?limit=50", headers=_headers_a())
        results["context"] = r1.json()
        results["summary"] = r2.json()
        results["courses"] = r3.json()
        results["enrollments"] = r4.json()
        return results

    async def fetch_b():
        results = {}
        r1 = await client.get("/api/v1/b2b/context", headers=_headers_b())
        r2 = await client.get("/api/v1/b2b/summary", headers=_headers_b())
        r3 = await client.get("/api/v1/b2b/courses?limit=50", headers=_headers_b())
        r4 = await client.get("/api/v1/b2b/enrollments?limit=50", headers=_headers_b())
        results["context"] = r1.json()
        results["summary"] = r2.json()
        results["courses"] = r3.json()
        results["enrollments"] = r4.json()
        return results

    tasks = []
    for _ in range(10):
        tasks.append(fetch_a())
        tasks.append(fetch_b())

    results = await asyncio.gather(*tasks)

    for i in range(0, len(results), 2):
        assert results[i]["context"]["tenant_id"] == str(TENANT_A_ID)
        assert results[i]["summary"]["active_courses"] == 1
        assert len(results[i]["courses"]["data"]) == 1
        assert results[i]["courses"]["data"][0]["code"] == "CONC-A"
        assert len(results[i]["enrollments"]["data"]) == 1
        assert results[i]["enrollments"]["data"][0]["course_name"] == "Concurrent Course A"
    for i in range(1, len(results), 2):
        assert results[i]["context"]["tenant_id"] == str(TENANT_B_ID)
        assert results[i]["summary"]["active_courses"] == 1
        assert len(results[i]["courses"]["data"]) == 1
        assert results[i]["courses"]["data"][0]["code"] == "CONC-B"
        assert len(results[i]["enrollments"]["data"]) == 1
        assert results[i]["enrollments"]["data"][0]["course_name"] == "Concurrent Course B"
