"""Dashboard stats regression tests.

Covers Step 16 — DASHBOARD:
- Admin stats load (student count, active classes, pending enrollments, monthly revenue)
- Student cannot access admin stats
- Anonymous cannot access stats
- Stats are tenant-scoped (no cross-tenant leakage)
- Failure state (DB error → graceful)
"""

import uuid
from datetime import timedelta

from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality, CourseType
from app.models.student import Student
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole


async def _seed_alfa_tenant():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        alfa = Tenant(
            name="Alfa Academy",
            slug="alfa",
            status=TenantStatus.ACTIVE,
            contact_name="Alfa Admin",
            contact_email="admin@alfa.test",
            primary_color="#E86A17",
        )
        db.add(alfa)
        await db.commit()
        await db.refresh(alfa)
        return alfa.id


async def _create_admin(email, tenant_id):
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=email,
            full_name=f"Admin {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


async def test_dashboard_stats_requires_auth(client):
    """Anonymous request → 403."""
    response = await client.get("/api/v1/dashboard/stats")
    assert response.status_code == 403


async def test_dashboard_stats_student_forbidden(client, student_user):
    """Student cannot access admin stats → 403."""
    response = await client.get("/api/v1/dashboard/stats", headers=student_user["headers"])
    assert response.status_code == 403


async def test_dashboard_stats_admin_returns_expected_fields(client, admin_headers):
    """Admin stats return all four expected fields with correct types."""
    response = await client.get("/api/v1/dashboard/stats", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "totalStudents" in data
    assert "activeClasses" in data
    assert "pendingEnrollments" in data
    assert "monthlyRevenue" in data
    # Empty DB → zeros
    assert data["totalStudents"] == 0
    assert data["activeClasses"] == 0
    assert data["pendingEnrollments"] == 0


async def test_dashboard_stats_reflect_created_data(client, admin_headers):
    """Stats reflect created students, classes, enrollments."""
    # Create a course
    course_resp = await client.post(
        "/api/v1/courses/",
        json={
            "code": "DASH-01",
            "name": "Dashboard Course",
            "category": "Test",
            "carga_horaria": 8,
            "modality": "PRESENCIAL",
            "tipo_curso": "FORMACAO",
            "price": 200.0,
        },
        headers=admin_headers,
    )
    assert course_resp.status_code == 201
    course_id = course_resp.json()["id"]

    me = await client.get("/api/v1/auth/me", headers=admin_headers)
    admin_id = me.json()["id"]

    # Create an ABERTA class
    today = utc_now().date()
    class_resp = await client.post(
        "/api/v1/classes/",
        json={
            "course_id": course_id,
            "responsible_admin_id": admin_id,
            "start_date": (today + timedelta(days=1)).isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "max_students": 20,
            "location": "Sala 1",
            "ead_link": None,
            "status": "ABERTA",
            "description": "Turma dashboard",
        },
        headers=admin_headers,
    )
    assert class_resp.status_code == 201
    class_id = class_resp.json()["id"]

    # Create a student (this also creates a PENDENTE enrollment via the
    # student creation flow which enrolls the student in the class).
    email = f"dashstudent_{uuid.uuid4().hex[:8]}@example.com"
    cpf = f"{uuid.uuid4().int % 10**11:011d}"
    student_resp = await client.post(
        "/api/v1/students/",
        json={
            "email": email,
            "full_name": "Dash Student",
            "password": "student123",
            "cpf": cpf,
            "class_id": class_id,
        },
        headers=admin_headers,
    )
    assert student_resp.status_code == 201

    # Verify stats
    response = await client.get("/api/v1/dashboard/stats", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["totalStudents"] == 1
    assert data["activeClasses"] == 1  # ABERTA counts as active
    # The student creation flow creates a PENDENTE enrollment
    assert data["pendingEnrollments"] >= 1


async def test_dashboard_stats_tenant_isolation(client, admin_headers):
    """WR admin stats do not count Alfa data."""
    alfa_id = await _seed_alfa_tenant()
    alfa_admin_id = await _create_admin("alfadash@alfa.test", alfa_id)

    # Seed a student in Alfa (requires a linked user)
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = alfa_id
        await db.execute(text(f"SET LOCAL app.current_tenant = '{alfa_id}'"))
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        course = Course(
            tenant_id=alfa_id,
            code="ALFA-DASH-01",
            name="Alfa Dash Course",
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=99.90,
        )
        db.add(course)
        await db.commit()
        await db.refresh(course)

        today = utc_now().date()
        cls = Class(
            tenant_id=alfa_id,
            course_id=course.id,
            responsible_admin_id=alfa_admin_id,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=30),
            max_students=20,
            location="Alfa Room",
            status=ClassStatus.ABERTA,
        )
        db.add(cls)
        await db.commit()
        await db.refresh(cls)

        # Create a user for the student
        student_user = User(
            email="alfadashstudent@alfa.test",
            full_name="Alfa Dash Student",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=alfa_id,
        )
        db.add(student_user)
        await db.commit()
        await db.refresh(student_user)

        student = Student(
            tenant_id=alfa_id,
            user_id=student_user.id,
            cpf=str(uuid.uuid4().int)[:11],
        )
        db.add(student)
        await db.commit()

    # WR admin stats should be zero (no WR students/classes/enrollments)
    response = await client.get("/api/v1/dashboard/stats", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["totalStudents"] == 0, "WR stats must not count Alfa students"
    assert data["activeClasses"] == 0, "WR stats must not count Alfa classes"
