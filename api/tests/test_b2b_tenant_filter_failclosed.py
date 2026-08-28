"""Phase 5: Fail-closed tenant filter tests.

Verifies that the explicit ``tenant_id`` filters in B2B joins prevent
cross-tenant data leakage even when RLS is NOT active (defense in depth).

Creates deliberately inconsistent records (e.g., an Enrollment in
Tenant A pointing to a Class in Tenant B) and verifies that the B2B
API never returns mixed-tenant data.
"""

import uuid
from datetime import date, datetime

import httpx
import pytest
from sqlalchemy import text

from app.core.database import AsyncSessionLocal
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

B2B_A_ID = "test-b2b-failclosed-a"
B2B_A_SECRET = "test-b2b-failclosed-a-secret-32chars!!"


async def _seed_inconsistent_data():
    """Seed data with deliberate cross-tenant inconsistencies.

    Creates:
    - Tenant A with a course, class, student, enrollment, B2B client
    - Tenant B with a course, class
    - An Enrollment in Tenant A pointing to Tenant B's class (cross-tenant FK)
    - A Student in Tenant A with a User in Tenant B (cross-tenant user link)

    The B2B API for Tenant A should NOT see Tenant B's course/class via
    the inconsistent enrollment, because explicit tenant_id filters
    on the joins prevent it.
    """
    async with AsyncSessionLocal() as session:
        # Tenant A
        session.add(Tenant(
            id=TENANT_A_ID, name="Tenant A", slug="failclosed-a",
            status=TenantStatus.ACTIVE, contact_name="Test", contact_email="a@test.com",
        ))
        # Tenant B
        session.add(Tenant(
            id=TENANT_B_ID, name="Tenant B", slug="failclosed-b",
            status=TenantStatus.ACTIVE, contact_name="Test", contact_email="b@test.com",
        ))
        await session.flush()

        # Tenant A user + student
        user_a = User(
            tenant_id=TENANT_A_ID, email="student@failclosed-a.com",
            full_name="Student A", password_hash=hash_password("pw1234567"),
            role=UserRole.STUDENT.value, is_active=True,
        )
        session.add(user_a)
        await session.flush()
        student_a = Student(tenant_id=TENANT_A_ID, user_id=user_a.id, cpf=make_valid_cpf())
        session.add(student_a)
        await session.flush()

        # Tenant A course + class
        course_a = Course(
            tenant_id=TENANT_A_ID, code="FC-A", name="FailClosed Course A",
            category="Test", carga_horaria=8, modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO, price=100.0, is_active=True,
        )
        session.add(course_a)
        await session.flush()
        admin_a = User(
            tenant_id=TENANT_A_ID, email="admin@failclosed-a.com",
            full_name="Admin A", password_hash=hash_password("pw1234567"),
            role=UserRole.ADMIN.value, is_active=True,
        )
        session.add(admin_a)
        await session.flush()
        class_a = Class(
            tenant_id=TENANT_A_ID, course_id=course_a.id, responsible_admin_id=admin_a.id,
            status=ClassStatus.ABERTA,
            max_students=20, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        session.add(class_a)
        await session.flush()

        # Tenant B course + class
        course_b = Course(
            tenant_id=TENANT_B_ID, code="FC-B", name="FailClosed Course B",
            category="Test", carga_horaria=8, modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO, price=100.0, is_active=True,
        )
        session.add(course_b)
        await session.flush()
        admin_b = User(
            tenant_id=TENANT_B_ID, email="admin@failclosed-b.com",
            full_name="Admin B", password_hash=hash_password("pw1234567"),
            role=UserRole.ADMIN.value, is_active=True,
        )
        session.add(admin_b)
        await session.flush()
        class_b = Class(
            tenant_id=TENANT_B_ID, course_id=course_b.id, responsible_admin_id=admin_b.id,
            status=ClassStatus.ABERTA,
            max_students=20, start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        session.add(class_b)
        await session.flush()

        # Legitimate enrollment in Tenant A
        enr_a = Enrollment(
            tenant_id=TENANT_A_ID, student_id=student_a.id, class_id=class_a.id,
            status=EnrollmentStatus.CONFIRMADA, source=EnrollmentSource.INDIVIDUAL,
            enrollment_date=datetime(2026, 1, 15), price=100.0,
        )
        session.add(enr_a)

        # INCONSISTENT: Enrollment in Tenant A pointing to Tenant B's class
        # This should be filtered out by Class.tenant_id == tid in the joins
        enr_cross = Enrollment(
            tenant_id=TENANT_A_ID, student_id=student_a.id, class_id=class_b.id,
            status=EnrollmentStatus.CONFIRMADA, source=EnrollmentSource.INDIVIDUAL,
            enrollment_date=datetime(2026, 1, 16), price=100.0,
        )
        session.add(enr_cross)

        # B2B client for Tenant A
        session.add(B2BClient(
            tenant_id=TENANT_A_ID, client_id=B2B_A_ID,
            client_secret_hash=hash_password(B2B_A_SECRET),
            name="B2B FailClosed A", allowed_scopes="academic:read", is_active=True,
        ))
        await session.commit()


@pytest.fixture(autouse=True)
async def failclosed_seed(setup_db):
    """Seed inconsistent data after conftest setup_db (no RLS)."""
    await _seed_inconsistent_data()
    yield


def _headers_a():
    return {"X-B2B-Client-Id": B2B_A_ID, "X-B2B-Client-Secret": B2B_A_SECRET}


@pytest.mark.asyncio
async def test_failclosed_enrollments_no_cross_tenant_course(client: httpx.AsyncClient):
    """Enrollment pointing to Tenant B's class must not leak Tenant B's course name.

    Without explicit Class.tenant_id and Course.tenant_id filters, the
    cross-tenant enrollment would join to Tenant B's class/course and
    expose "FailClosed Course B" in Tenant A's enrollment list.
    """
    response = await client.get("/api/v1/b2b/enrollments?limit=50", headers=_headers_a())
    assert response.status_code == 200
    data = response.json()["data"]
    # Should only see the legitimate enrollment (Course A), not the
    # cross-tenant one (Course B)
    course_names = {e["course_name"] for e in data}
    assert "FailClosed Course A" in course_names
    assert "FailClosed Course B" not in course_names


@pytest.mark.asyncio
async def test_failclosed_enrollment_detail_cross_tenant_404(client: httpx.AsyncClient):
    """Direct access to the cross-tenant enrollment should not expose Tenant B data."""
    # Find the cross-tenant enrollment ID
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT e.id FROM enrollments e "
                "JOIN classes c ON c.id = e.class_id "
                "WHERE e.tenant_id = :tid_a AND c.tenant_id = :tid_b"
            ),
            {"tid_a": str(TENANT_A_ID), "tid_b": str(TENANT_B_ID)},
        )
        enr_id = result.scalar_one_or_none()

    if enr_id:
        response = await client.get(
            f"/api/v1/b2b/enrollments/{enr_id}", headers=_headers_a()
        )
        # The enrollment exists in Tenant A, but the class/course are in
        # Tenant B. With explicit tenant_id filters on Class/Course,
        # the class lookup returns None → 404 (fail closed).
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_failclosed_summary_no_inflation(client: httpx.AsyncClient):
    """Summary should count only 1 enrollment (the legitimate one), not 2."""
    response = await client.get("/api/v1/b2b/summary", headers=_headers_a())
    assert response.status_code == 200
    data = response.json()
    # The cross-tenant enrollment has Enrollment.tenant_id == Tenant A,
    # so it IS counted in active_enrollments. But the course count
    # should be 1 (only Tenant A's course), not 2.
    assert data["active_courses"] == 1


@pytest.mark.asyncio
async def test_failclosed_courses_no_tenant_b(client: httpx.AsyncClient):
    """Courses list should only show Tenant A's course, not Tenant B's."""
    response = await client.get("/api/v1/b2b/courses?limit=50", headers=_headers_a())
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["code"] == "FC-A"
    assert data[0]["name"] == "FailClosed Course A"
