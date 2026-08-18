"""Two-tenant data isolation tests (WR + Alfa).

Verifies that data created in one tenant is NOT visible to the other
tenant's admin, even when both tenants share the same database.

These tests use the privileged session (RLS bypass) to seed data in
both tenants, then use the HTTP API with each tenant's admin token +
X-Tenant-Slug to verify isolation at the application layer.
"""

import uuid

import pytest
from sqlalchemy import select

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.course import Course, CourseModality, CourseType
from app.models.student import Student
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole


async def _seed_alfa_tenant():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await db.execute(
            __import__("sqlalchemy").text(
                f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"
            )
        )
        await db.execute(__import__("sqlalchemy").text("SET LOCAL app.bypass_rls = '1'"))
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
        await db.execute(
            __import__("sqlalchemy").text(
                f"SET LOCAL app.current_tenant = '{tenant_id}'"
            )
        )
        await db.execute(__import__("sqlalchemy").text("SET LOCAL app.bypass_rls = '1'"))
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


async def _create_course(tenant_id, code, name):
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(
            __import__("sqlalchemy").text(
                f"SET LOCAL app.current_tenant = '{tenant_id}'"
            )
        )
        await db.execute(__import__("sqlalchemy").text("SET LOCAL app.bypass_rls = '1'"))
        course = Course(
            tenant_id=tenant_id,
            code=code,
            name=name,
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=99.90,
        )
        db.add(course)
        await db.commit()
        return course.id


@pytest.mark.asyncio
async def test_wr_admin_does_not_see_alfa_courses(client):
    """WR admin listando cursos não vê cursos do tenant Alfa."""
    alfa_id = await _seed_alfa_tenant()
    # Create a course in Alfa
    alfa_course_id = await _create_course(alfa_id, "ALFA-ISO-01", "Alfa Isolation Test")
    # Create a course in WR (via privileged session)
    wr_course_id = await _create_course(WR_TENANT_ID, "WR-ISO-01", "WR Isolation Test")

    wr_admin_id = await _create_admin("isowr@wr.test", WR_TENANT_ID)
    token = create_access_token(
        {"sub": str(wr_admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
    )

    # Use admin-protected endpoint (POST /courses requires admin)
    # GET /courses/ is public, but we can verify via admin listing
    resp = await client.get(
        "/api/v1/courses/",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    courses = resp.json()
    codes = [c["code"] for c in courses]
    assert "WR-ISO-01" in codes
    assert "ALFA-ISO-01" not in codes, "WR admin should NOT see Alfa courses"


@pytest.mark.asyncio
async def test_alfa_admin_does_not_see_wr_courses(client):
    """Alfa admin listando cursos não vê cursos do tenant WR."""
    alfa_id = await _seed_alfa_tenant()
    await _create_course(alfa_id, "ALFA-ISO-02", "Alfa Isolation Test 2")
    await _create_course(WR_TENANT_ID, "WR-ISO-02", "WR Isolation Test 2")

    alfa_admin_id = await _create_admin("isoalfa@alfa.test", alfa_id)
    token = create_access_token(
        {"sub": str(alfa_admin_id), "role": "admin", "tenant_id": str(alfa_id)}
    )

    resp = await client.get(
        "/api/v1/courses/",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code == 200
    courses = resp.json()
    codes = [c["code"] for c in courses]
    assert "ALFA-ISO-02" in codes
    assert "WR-ISO-02" not in codes, "Alfa admin should NOT see WR courses"


@pytest.mark.asyncio
async def test_alfa_admin_cannot_create_course_in_wr(client):
    """Alfa admin não pode criar curso em WR (JWT tenant binding)."""
    alfa_id = await _seed_alfa_tenant()
    alfa_admin_id = await _create_admin("createalfa@alfa.test", alfa_id)
    token = create_access_token(
        {"sub": str(alfa_admin_id), "role": "admin", "tenant_id": str(alfa_id)}
    )

    # Try to create a course with WR slug → 403 (JWT mismatch)
    resp = await client.post(
        "/api/v1/courses/",
        json={
            "code": "HACK-01",
            "name": "Hacked Course",
            "category": "Test",
            "carga_horaria": 8,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 99.90,
        },
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_alfa_admin_can_create_course_in_alfa(client):
    """Alfa admin pode criar curso em Alfa (mesmo tenant)."""
    alfa_id = await _seed_alfa_tenant()
    alfa_admin_id = await _create_admin("createok@alfa.test", alfa_id)
    token = create_access_token(
        {"sub": str(alfa_admin_id), "role": "admin", "tenant_id": str(alfa_id)}
    )

    resp = await client.post(
        "/api/v1/courses/",
        json={
            "code": "ALFA-OK-01",
            "name": "Alfa OK Course",
            "category": "Test",
            "carga_horaria": 8,
            "modality": "EAD",
            "tipo_curso": "FORMACAO",
            "price": 99.90,
        },
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
    )
    assert resp.status_code in (200, 201)
