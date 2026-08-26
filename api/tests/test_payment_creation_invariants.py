import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException

from app.api.routes.payments import create_payment, create_payment_admin
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.payment import PaymentAdminCreate, PaymentCreate


async def _seed_pending_enrollment(*, price: float = 100.0):
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        admin = User(
            tenant_id=WR_TENANT_ID,
            email=f"payment-admin-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Admin Payment",
            cpf=str(uuid.uuid4().int)[-11:],
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        user = User(
            tenant_id=WR_TENANT_ID,
            email=f"payment-student-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Aluno Payment",
            cpf=str(uuid.uuid4().int)[-11:],
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"PAY-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Payment",
            category="Segurança",
            carga_horaria=8,
            modality="EAD",
            price=price,
            is_active=True,
        )
        db.add_all([admin, user, course])
        await db.flush()

        student = Student(
            tenant_id=WR_TENANT_ID,
            user_id=user.id,
            cpf=user.cpf,
        )
        class_obj = Class(
            tenant_id=WR_TENANT_ID,
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today,
            end_date=today + timedelta(days=30),
            max_students=20,
            status=ClassStatus.ABERTA,
        )
        db.add_all([student, class_obj])
        await db.flush()

        enrollment = Enrollment(
            tenant_id=WR_TENANT_ID,
            student_id=student.id,
            class_id=class_obj.id,
            price=price,
            status=EnrollmentStatus.PENDENTE,
        )
        db.add(enrollment)
        await db.commit()
        return enrollment.id, admin.id


@pytest.mark.asyncio
async def test_direct_payment_creation_reuses_active_attempt():
    enrollment_id, admin_id = await _seed_pending_enrollment()
    async with AsyncSessionLocal() as db:
        existing = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment_id,
            amount=100.0,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
            provider_payment_id="active-provider-payment",
        )
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        existing_id = existing.id

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            result = await create_payment(
                PaymentCreate(enrollment_id=enrollment_id, method=PaymentMethod.PIX),
                db,
                {"user_id": str(admin_id), "role": "admin"},
            )
    finally:
        current_tenant_id.reset(token)

    assert result.id == existing_id
    assert result.status == PaymentStatus.PROCESSANDO


@pytest.mark.asyncio
async def test_admin_manual_payment_conflicts_with_active_attempt():
    enrollment_id, admin_id = await _seed_pending_enrollment()
    async with AsyncSessionLocal() as db:
        db.add(
            Payment(
                tenant_id=WR_TENANT_ID,
                enrollment_id=enrollment_id,
                amount=100.0,
                status=PaymentStatus.PENDENTE,
                method=PaymentMethod.PIX,
            )
        )
        await db.commit()

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            with pytest.raises(HTTPException) as exc:
                await create_payment_admin(
                    PaymentAdminCreate(
                        enrollment_id=enrollment_id,
                        amount=120.0,
                        method=PaymentMethod.PIX,
                    ),
                    db,
                    {"user_id": str(admin_id), "role": "admin"},
                )
    finally:
        current_tenant_id.reset(token)

    assert exc.value.status_code == 409
    assert "active payment attempt" in exc.value.detail


@pytest.mark.asyncio
async def test_admin_manual_payment_rejects_non_positive_amount():
    enrollment_id, admin_id = await _seed_pending_enrollment()

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            with pytest.raises(HTTPException) as exc:
                await create_payment_admin(
                    PaymentAdminCreate(
                        enrollment_id=enrollment_id,
                        amount=0.0,
                        method=PaymentMethod.PIX,
                    ),
                    db,
                    {"user_id": str(admin_id), "role": "admin"},
                )
    finally:
        current_tenant_id.reset(token)

    assert exc.value.status_code == 400
    assert "greater than zero" in exc.value.detail


@pytest.mark.asyncio
async def test_direct_payment_rejects_confirmed_enrollment():
    enrollment_id, admin_id = await _seed_pending_enrollment()
    async with AsyncSessionLocal() as db:
        enrollment = await db.get(Enrollment, enrollment_id)
        enrollment.status = EnrollmentStatus.CONFIRMADA
        await db.commit()

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            with pytest.raises(HTTPException) as exc:
                await create_payment(
                    PaymentCreate(
                        enrollment_id=enrollment_id,
                        method=PaymentMethod.PIX,
                    ),
                    db,
                    {"user_id": str(admin_id), "role": "admin"},
                )
    finally:
        current_tenant_id.reset(token)

    assert exc.value.status_code == 409
    assert "not pending payment" in exc.value.detail
