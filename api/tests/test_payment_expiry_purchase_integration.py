import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.api.routes.enrollments import purchase_enrollment
from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import EnrollmentStatus
from app.models.payment import Payment, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.enrollment import EnrollmentPurchaseRequest


async def _seed_paid_course():
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        admin = User(
            tenant_id=WR_TENANT_ID,
            email=f"expiry-admin-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Admin Expiry",
            cpf=str(uuid.uuid4().int)[-11:],
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        user = User(
            tenant_id=WR_TENANT_ID,
            email=f"expiry-student-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Aluno Expiry",
            cpf=str(uuid.uuid4().int)[-11:],
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"EXP-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Expiração",
            category="Segurança",
            carga_horaria=8,
            modality="EAD",
            price=199.0,
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
        await db.commit()
        return course.id, user.id


@pytest.mark.asyncio
async def test_stale_internal_attempt_is_expired_and_replaced(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PENDING_ATTEMPT_TTL_MINUTES", 30)
    course_id, user_id = await _seed_paid_course()
    current_user = {
        "user_id": str(user_id),
        "role": "student",
        "tenant_id": str(WR_TENANT_ID),
    }
    data = EnrollmentPurchaseRequest(course_id=course_id)

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        first = await purchase_enrollment(data, db, current_user)
        first_payment_id = first.payment.id
        enrollment_id = first.enrollment.id

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, first_payment_id)
        payment.created_at = utc_now() - timedelta(minutes=31)
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        retry = await purchase_enrollment(data, db, current_user)

    assert retry.enrollment.id == enrollment_id
    assert retry.enrollment.status == EnrollmentStatus.PENDENTE
    assert retry.payment.id != first_payment_id
    assert retry.payment.status == PaymentStatus.PENDENTE

    async with AsyncSessionLocal() as db:
        attempts = (
            await db.execute(
                select(Payment)
                .where(Payment.enrollment_id == enrollment_id)
                .order_by(Payment.created_at.asc(), Payment.id.asc())
            )
        ).scalars().all()

    assert len(attempts) == 2
    expired = next(p for p in attempts if p.id == first_payment_id)
    assert expired.status == PaymentStatus.EXPIRADO


@pytest.mark.asyncio
async def test_old_external_charge_is_reused_instead_of_locally_expired(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PENDING_ATTEMPT_TTL_MINUTES", 30)
    course_id, user_id = await _seed_paid_course()
    current_user = {
        "user_id": str(user_id),
        "role": "student",
        "tenant_id": str(WR_TENANT_ID),
    }
    data = EnrollmentPurchaseRequest(course_id=course_id)

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        first = await purchase_enrollment(data, db, current_user)
        first_payment_id = first.payment.id

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, first_payment_id)
        payment.created_at = utc_now() - timedelta(days=2)
        payment.status = PaymentStatus.PROCESSANDO
        payment.provider_payment_id = "external-still-payable"
        payment.checkout_url = "https://payments.example/still-payable"
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        resumed = await purchase_enrollment(data, db, current_user)

    assert resumed.payment.id == first_payment_id
    assert resumed.payment.status == PaymentStatus.PROCESSANDO
    assert resumed.payment.provider_payment_id == "external-still-payable"
