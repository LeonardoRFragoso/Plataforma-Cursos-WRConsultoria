"""Tests for corporate flow — employees must NOT get individual charges."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.company import Company
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
from app.models.payment import Payment
from app.models.student import Student
from app.models.user import User, UserRole


async def _setup_corporate_context():
    """Create admin, company, course, class, and 3 corporate students."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))

        admin = User(
            email=f"corp_admin_{uuid.uuid4().hex[:6]}@wr.test",
            full_name="Corp Admin",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)
        await db.flush()

        company = Company(
            tenant_id=WR_TENANT_ID,
            legal_name="Corp Test Ltd",
            cnpj="12345678000190",
            rh_name="RH",
            rh_email="rh@corp.test",
            rh_phone="11888888888",
        )
        db.add(company)
        await db.flush()

        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"CORP-{uuid.uuid4().hex[:6].upper()}",
            name="Corporate Course",
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=200.0,
            is_active=True,
        )
        db.add(course)
        await db.flush()

        start = utc_now().date() + timedelta(days=1)
        cls = Class(
            tenant_id=WR_TENANT_ID,
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=start,
            end_date=start + timedelta(days=30),
            max_students=50,
            status=ClassStatus.ABERTA,
        )
        db.add(cls)
        await db.flush()

        # Create 3 corporate students
        student_ids = []
        for i in range(3):
            user = User(
                email=f"corp_stu_{i}_{uuid.uuid4().hex[:6]}@wr.test",
                full_name=f"Corp Student {i}",
                cpf=str(uuid.uuid4().int)[:11],
                password_hash=hash_password("pass123"),
                role=UserRole.STUDENT,
                is_active=True,
                tenant_id=WR_TENANT_ID,
            )
            db.add(user)
            await db.flush()

            student = Student(
                user_id=user.id,
                tenant_id=WR_TENANT_ID,
                cpf=str(uuid.uuid4().int)[:11],
                company_id=company.id,
            )
            db.add(student)
            await db.flush()
            student_ids.append(student.id)

        await db.commit()
        return {
            "admin_id": admin.id,
            "company_id": company.id,
            "course_id": course.id,
            "class_id": cls.id,
            "student_ids": student_ids,
        }


def _headers(user_id, role="admin", tenant_id=WR_TENANT_ID):
    token = create_access_token(
        {"sub": str(user_id), "role": role, "tenant_id": str(tenant_id)}
    )
    return {"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"}


@pytest.mark.asyncio
async def test_corporate_bulk_no_individual_payments(client):
    """Corporate bulk enrollment with create_payment=False creates 0 payments."""
    ctx = await _setup_corporate_context()

    resp = await client.post(
        "/api/v1/enrollments/bulk",
        json={
            "class_id": str(ctx["class_id"]),
            "student_ids": [str(sid) for sid in ctx["student_ids"]],
            "company_id": str(ctx["company_id"]),
            "price_per_student": 200.0,
            "source": "CORPORATE",
            "status": "CONFIRMADA",
            "create_payment": False,
        },
        headers=_headers(ctx["admin_id"]),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["payment_id"] is None  # No payment created

    # Verify no payments exist for these enrollments
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        enrollments = (await db.execute(
            select(Enrollment).where(
                Enrollment.student_id.in_(ctx["student_ids"]),
                Enrollment.class_id == ctx["class_id"],
            )
        )).scalars().all()
        assert len(enrollments) == 3
        for e in enrollments:
            assert e.source == EnrollmentSource.CORPORATE
            assert e.status == EnrollmentStatus.CONFIRMADA

        # Check no payments linked to these enrollments
        payments = (await db.execute(
            select(Payment).where(
                Payment.enrollment_id.in_([e.id for e in enrollments])
            )
        )).scalars().all()
        assert len(payments) == 0


@pytest.mark.asyncio
async def test_corporate_bulk_consolidated_payment(client):
    """Corporate bulk with create_payment=True creates ONE consolidated payment."""
    ctx = await _setup_corporate_context()

    resp = await client.post(
        "/api/v1/enrollments/bulk",
        json={
            "class_id": str(ctx["class_id"]),
            "student_ids": [str(sid) for sid in ctx["student_ids"]],
            "company_id": str(ctx["company_id"]),
            "price_per_student": 200.0,
            "source": "CORPORATE",
            "status": "CONFIRMADA",
            "create_payment": True,
            "payment_method": "PIX",
        },
        headers=_headers(ctx["admin_id"]),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["payment_id"] is not None  # One consolidated payment
    assert data["total_amount"] == 600.0  # 200 * 3

    # Verify exactly ONE payment, linked to company not enrollments
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        payment = (await db.execute(
            select(Payment).where(Payment.id == uuid.UUID(data["payment_id"]))
        )).scalar_one()
        assert payment.company_id == ctx["company_id"]
        assert payment.enrollment_id is None  # Not linked to individual enrollment
        assert payment.amount == 600.0

        # Verify no individual payments for the enrollments
        enrollments = (await db.execute(
            select(Enrollment).where(
                Enrollment.student_id.in_(ctx["student_ids"]),
                Enrollment.class_id == ctx["class_id"],
            )
        )).scalars().all()
        individual_payments = (await db.execute(
            select(Payment).where(
                Payment.enrollment_id.in_([e.id for e in enrollments])
            )
        )).scalars().all()
        assert len(individual_payments) == 0
