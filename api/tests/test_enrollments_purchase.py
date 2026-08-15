import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.api.routes.enrollments import purchase_enrollment
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import EnrollmentStatus
from app.models.payment import PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.enrollment import EnrollmentPurchaseRequest


async def _seed_purchase_data():
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID

        admin = User(
            email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Admin",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)

        student_user = User(
            email=f"student_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Student",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(student_user)

        course = Course(
            code=f"C-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Comprável",
            category="Segurança",
            carga_horaria=40,
            modality="PRESENCIAL",
            price=150.0,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(course)

        await db.flush()

        cls = Class(
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today,
            end_date=today + timedelta(days=30),
            max_students=20,
            status=ClassStatus.ABERTA,
            tenant_id=WR_TENANT_ID,
        )
        db.add(cls)

        student = Student(
            user_id=student_user.id,
            cpf="52988744005",
            phone="(11) 99999-9999",
            tenant_id=WR_TENANT_ID,
        )
        db.add(student)

        await db.commit()

        return course.id, cls.id, student.id, student_user.id


@pytest.mark.asyncio
async def test_purchase_enrollment_creates_payment():
    course_id, class_id, student_id, user_id = await _seed_purchase_data()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)
        result = await purchase_enrollment(data, db, current_user)

    assert result.enrollment.student_id == student_id
    assert result.enrollment.class_id == class_id
    assert result.enrollment.status == EnrollmentStatus.PENDENTE
    assert result.payment.status == PaymentStatus.PENDENTE
    assert result.payment.amount == 150.0
    assert result.payment.method.value == "BOLETO"


@pytest.mark.asyncio
async def test_purchase_enrollment_is_idempotent():
    course_id, _, _, user_id = await _seed_purchase_data()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=course_id)

        first = await purchase_enrollment(data, db, current_user)
        second = await purchase_enrollment(data, db, current_user)

    assert first.enrollment.id == second.enrollment.id
    assert first.payment.id == second.payment.id


@pytest.mark.asyncio
async def test_purchase_enrollment_rejects_non_student():
    course_id, *_ = await _seed_purchase_data()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(uuid.uuid4()), "role": "admin"}
        data = EnrollmentPurchaseRequest(course_id=course_id)

        with pytest.raises(HTTPException) as exc:
            await purchase_enrollment(data, db, current_user)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_purchase_enrollment_course_not_found():
    _, _, _, user_id = await _seed_purchase_data()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        current_user = {"user_id": str(user_id), "role": "student"}
        data = EnrollmentPurchaseRequest(course_id=uuid.uuid4())

        with pytest.raises(HTTPException) as exc:
            await purchase_enrollment(data, db, current_user)
        assert exc.value.status_code == 404
