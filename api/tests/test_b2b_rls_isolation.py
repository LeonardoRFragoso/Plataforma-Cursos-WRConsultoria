"""PostgreSQL integration test for B2B RLS cross-tenant isolation.

This test creates two tenants with academic data and verifies that:
- B2BClient A (Tenant A) only sees Tenant A's data
- B2BClient B (Tenant B) only sees Tenant B's data
- Cross-tenant access never occurs

Unlike the main test suite (which uses create_all without RLS policies),
this test explicitly enables RLS on the academic tables to verify that
the ``set_config('app.current_tenant', :tid, true)`` approach correctly
scopes queries at the PostgreSQL level.

Requires a PostgreSQL test database (not SQLite).
"""

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

B2B_A_ID = "test-b2b-tenant-a"
B2B_A_SECRET = "test-b2b-tenant-a-secret-32chars-pad!!"
B2B_B_ID = "test-b2b-tenant-b"
B2B_B_SECRET = "test-b2b-tenant-b-secret-32chars-pad!!"

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
    """Create a tenant, course, class, enrollment, and B2B client."""
    async with AsyncSessionLocal() as session:
        session.info["tenant_id"] = tenant_id
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        await session.execute(text("SET LOCAL app.bypass_rls = '1'"))

        # Tenant
        session.add(Tenant(
            id=tenant_id, name=f"Tenant {slug.upper()}", slug=slug,
            status=TenantStatus.ACTIVE, contact_name="Test", contact_email=f"test@{slug}.com",
        ))
        await session.flush()

        # Users
        student_user = User(
            tenant_id=tenant_id, email=f"student@{slug}.com",
            full_name=f"Student {slug}", password_hash=hash_password("password123"),
            role=UserRole.STUDENT.value, is_active=True,
        )
        admin_user = User(
            tenant_id=tenant_id, email=f"admin@{slug}.com",
            full_name=f"Admin {slug}", password_hash=hash_password("password123"),
            role=UserRole.ADMIN.value, is_active=True,
        )
        session.add_all([student_user, admin_user])
        await session.flush()

        # Student
        student = Student(tenant_id=tenant_id, user_id=student_user.id, cpf=make_valid_cpf())
        session.add(student)
        await session.flush()

        # Course
        course = Course(
            tenant_id=tenant_id, code=course_code, name=course_name,
            category="Test", carga_horaria=8, modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO, price=100.0, is_active=True,
        )
        session.add(course)
        await session.flush()

        # Class
        cls = Class(
            tenant_id=tenant_id, course_id=course.id, responsible_admin_id=admin_user.id,
            status=ClassStatus.ABERTA,
            max_students=20, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        session.add(cls)
        await session.flush()

        # Enrollment
        enrollment = Enrollment(
            tenant_id=tenant_id, student_id=student.id, class_id=cls.id,
            status=EnrollmentStatus.CONFIRMADA, source=EnrollmentSource.INDIVIDUAL,
            enrollment_date=datetime(2026, 1, 15), price=100.0,
        )
        session.add(enrollment)

        # B2B client
        session.add(B2BClient(
            tenant_id=tenant_id, client_id=b2b_id,
            client_secret_hash=hash_password(b2b_secret),
            name=f"B2B {slug}", allowed_scopes="academic:read", is_active=True,
        ))
        await session.commit()


@pytest.fixture(autouse=True)
async def rls_seed(setup_db):
    """Enable RLS and seed two tenants after the conftest setup_db runs."""
    await _enable_rls()
    await _seed_tenant(TENANT_A_ID, "tenant-a", "COURSE-A", "Course A", B2B_A_ID, B2B_A_SECRET)
    await _seed_tenant(TENANT_B_ID, "tenant-b", "COURSE-B", "Course B", B2B_B_ID, B2B_B_SECRET)
    yield
    await _disable_rls()


def _headers_a():
    return {"X-B2B-Client-Id": B2B_A_ID, "X-B2B-Client-Secret": B2B_A_SECRET}


def _headers_b():
    return {"X-B2B-Client-Id": B2B_B_ID, "X-B2B-Client-Secret": B2B_B_SECRET}


@pytest.mark.asyncio
async def test_rls_tenant_a_sees_only_a_courses(client: httpx.AsyncClient):
    """Tenant A's B2B client should only see Tenant A's courses."""
    response = await client.get("/api/v1/b2b/courses?limit=50", headers=_headers_a())
    assert response.status_code == 200
    data = response.json()
    for course in data["data"]:
        assert course["code"] == "COURSE-A"
        assert course["name"] == "Course A"


@pytest.mark.asyncio
async def test_rls_tenant_b_sees_only_b_courses(client: httpx.AsyncClient):
    """Tenant B's B2B client should only see Tenant B's courses."""
    response = await client.get("/api/v1/b2b/courses?limit=50", headers=_headers_b())
    assert response.status_code == 200
    data = response.json()
    for course in data["data"]:
        assert course["code"] == "COURSE-B"
        assert course["name"] == "Course B"


@pytest.mark.asyncio
async def test_rls_tenant_a_cannot_access_tenant_b_course(client: httpx.AsyncClient):
    """Tenant A's B2B client should get 404 for Tenant B's course."""
    resp_b = await client.get("/api/v1/b2b/courses?limit=1", headers=_headers_b())
    course_b_id = resp_b.json()["data"][0]["id"]
    response = await client.get(f"/api/v1/b2b/courses/{course_b_id}", headers=_headers_a())
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rls_tenant_b_cannot_access_tenant_a_course(client: httpx.AsyncClient):
    """Tenant B's B2B client should get 404 for Tenant A's course."""
    resp_a = await client.get("/api/v1/b2b/courses?limit=1", headers=_headers_a())
    course_a_id = resp_a.json()["data"][0]["id"]
    response = await client.get(f"/api/v1/b2b/courses/{course_a_id}", headers=_headers_b())
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rls_summary_tenant_a(client: httpx.AsyncClient):
    """Tenant A's summary should show 1 course, not 2."""
    response = await client.get("/api/v1/b2b/summary", headers=_headers_a())
    assert response.status_code == 200
    data = response.json()
    assert data["active_courses"] == 1
    assert data["active_enrollments"] == 1


@pytest.mark.asyncio
async def test_rls_summary_tenant_b(client: httpx.AsyncClient):
    """Tenant B's summary should show 1 course, not 2."""
    response = await client.get("/api/v1/b2b/summary", headers=_headers_b())
    assert response.status_code == 200
    data = response.json()
    assert data["active_courses"] == 1
    assert data["active_enrollments"] == 1


@pytest.mark.asyncio
async def test_rls_context_tenant_a(client: httpx.AsyncClient):
    """Tenant A's context should return Tenant A's UUID."""
    response = await client.get("/api/v1/b2b/context", headers=_headers_a())
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(TENANT_A_ID)
    assert data["tenant_slug"] == "tenant-a"


@pytest.mark.asyncio
async def test_rls_context_tenant_b(client: httpx.AsyncClient):
    """Tenant B's context should return Tenant B's UUID."""
    response = await client.get("/api/v1/b2b/context", headers=_headers_b())
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(TENANT_B_ID)
    assert data["tenant_slug"] == "tenant-b"


@pytest.mark.asyncio
async def test_rls_enrollments_isolated(client: httpx.AsyncClient):
    """Each tenant should only see their own enrollments."""
    resp_a = await client.get("/api/v1/b2b/enrollments?limit=50", headers=_headers_a())
    resp_b = await client.get("/api/v1/b2b/enrollments?limit=50", headers=_headers_b())
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    a_data = resp_a.json()["data"]
    b_data = resp_b.json()["data"]
    assert len(a_data) == 1
    assert len(b_data) == 1
    assert a_data[0]["id"] != b_data[0]["id"]
    assert a_data[0]["course_name"] == "Course A"
    assert b_data[0]["course_name"] == "Course B"
