import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes.enrollments import purchase_enrollment
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.enrollment import EnrollmentPurchaseRequest


def _unique_cpf() -> str:
    """Return an 11-digit unique value for direct model fixtures."""
    return str(uuid.uuid4().int)[-11:]


async def _seed_course(*, price: float):
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID

        admin = User(
            email=f"admin-b2c-{uuid.uuid4().hex[:10]}@test.com",
            full_name="Admin B2C",
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        student_user = User(
            email=f"student-b2c-{uuid.uuid4().hex[:10]}@test.com",
            full_name="Aluno B2C",
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        course = Course(
            code=f"B2C-{uuid.uuid4().hex[:8].upper()}",
            name="Curso Jornada B2C",
            category="Segurança",
            carga_horaria=8,
            modality="EAD",
            price=price,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add_all([admin, student_user, course])
        await db.flush()

        class_obj = Class(
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=today,
            end_date=today + timedelta(days=30),
            max_students=20,
            status=ClassStatus.ABERTA,
            tenant_id=WR_TENANT_ID,
        )
        student = Student(
            user_id=student_user.id,
            cpf=_unique_cpf(),
            tenant_id=WR_TENANT_ID,
        )
        db.add_all([class_obj, student])
        await db.commit()

        return course.id, class_obj.id, student.id, student_user.id


@pytest.mark.asyncio
async def test_free_course_confirms_enrollment_without_payment():
    """PAY-FREE-001: free course bypasses the gateway completely."""
    course_id, class_id, student_id, user_id = await _seed_course(price=0.0)
    current_user = {
        "user_id": str(user_id),
        "role": "student",
        "tenant_id": str(WR_TENANT_ID),
    }

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        result = await purchase_enrollment(
            EnrollmentPurchaseRequest(course_id=course_id),
            db,
            current_user,
        )

    assert result.enrollment.student_id == student_id
    assert result.enrollment.class_id == class_id
    assert result.enrollment.price == 0
    assert result.enrollment.status == EnrollmentStatus.CONFIRMADA
    assert result.payment is None

    async with AsyncSessionLocal() as db:
        payments = (
            await db.execute(
                select(Payment).where(Payment.enrollment_id == result.enrollment.id)
            )
        ).scalars().all()
    assert payments == []


@pytest.mark.asyncio
async def test_free_course_purchase_is_idempotent():
    """Repeated free enrollment returns the same access and creates no payment."""
    course_id, _, _, user_id = await _seed_course(price=0.0)
    current_user = {
        "user_id": str(user_id),
        "role": "student",
        "tenant_id": str(WR_TENANT_ID),
    }
    data = EnrollmentPurchaseRequest(course_id=course_id)

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        first = await purchase_enrollment(data, db, current_user)
        second = await purchase_enrollment(data, db, current_user)

    assert first.enrollment.id == second.enrollment.id
    assert second.enrollment.status == EnrollmentStatus.CONFIRMADA
    assert first.payment is None
    assert second.payment is None

    async with AsyncSessionLocal() as db:
        payments = (
            await db.execute(
                select(Payment).where(Payment.enrollment_id == first.enrollment.id)
            )
        ).scalars().all()
    assert payments == []


@pytest.mark.asyncio
async def test_rejected_payment_creates_new_attempt_and_preserves_history():
    """PAY-RETRY-001: rejected attempt is immutable history, not overwritten."""
    course_id, _, _, user_id = await _seed_course(price=180.0)
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
        first_payment = await db.get(Payment, first_payment_id)
        first_payment.status = PaymentStatus.RECUSADO
        first_payment.provider_payment_id = "provider-rejected-attempt"
        first_payment.checkout_url = "https://payments.example/rejected-attempt"
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        retry = await purchase_enrollment(data, db, current_user)

    assert retry.enrollment.id == enrollment_id
    assert retry.enrollment.status == EnrollmentStatus.PENDENTE
    assert retry.payment.id != first_payment_id
    assert retry.payment.status == PaymentStatus.PENDENTE
    assert retry.payment.amount == 180.0

    async with AsyncSessionLocal() as db:
        attempts = (
            await db.execute(
                select(Payment)
                .where(Payment.enrollment_id == enrollment_id)
                .order_by(Payment.created_at.asc(), Payment.id.asc())
            )
        ).scalars().all()

    assert len(attempts) == 2
    old_attempt = next(payment for payment in attempts if payment.id == first_payment_id)
    assert old_attempt.status == PaymentStatus.RECUSADO
    assert old_attempt.provider_payment_id == "provider-rejected-attempt"
    assert old_attempt.checkout_url == "https://payments.example/rejected-attempt"


@pytest.mark.asyncio
async def test_retry_is_idempotent_after_new_active_attempt():
    """After retry creation, refresh/double-click reuses the active attempt."""
    course_id, _, _, user_id = await _seed_course(price=220.0)
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
        payment.status = PaymentStatus.RECUSADO
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        retry = await purchase_enrollment(data, db, current_user)
        repeated = await purchase_enrollment(data, db, current_user)

    assert retry.enrollment.id == repeated.enrollment.id
    assert retry.payment.id == repeated.payment.id
    assert retry.payment.id != first_payment_id


@pytest.mark.asyncio
async def test_approved_payment_with_pending_enrollment_requires_manual_reconciliation():
    """An anomalous approved/pending state must never start a second charge."""
    course_id, _, _, user_id = await _seed_course(price=310.0)
    current_user = {
        "user_id": str(user_id),
        "role": "student",
        "tenant_id": str(WR_TENANT_ID),
    }
    data = EnrollmentPurchaseRequest(course_id=course_id)

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        first = await purchase_enrollment(data, db, current_user)
        payment_id = first.payment.id
        enrollment_id = first.enrollment.id

    # Simulate an approved provider payment that did not unlock the enrollment,
    # e.g. because reconciliation detected an amount mismatch.
    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        payment.status = PaymentStatus.APROVADO
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        with pytest.raises(HTTPException) as exc:
            await purchase_enrollment(data, db, current_user)

    assert exc.value.status_code == 409
    assert "manual reconciliation" in exc.value.detail

    async with AsyncSessionLocal() as db:
        attempts = (
            await db.execute(
                select(Payment).where(Payment.enrollment_id == enrollment_id)
            )
        ).scalars().all()
    assert len(attempts) == 1
    assert attempts[0].id == payment_id
    assert attempts[0].status == PaymentStatus.APROVADO


@pytest.mark.asyncio
async def test_free_legacy_pending_enrollment_is_reconciled_without_payment():
    """Legacy PENDENTE free enrollment becomes confirmed on the next purchase action."""
    course_id, class_id, student_id, user_id = await _seed_course(price=0.0)

    async with AsyncSessionLocal() as db:
        legacy = Enrollment(
            tenant_id=WR_TENANT_ID,
            student_id=student_id,
            class_id=class_id,
            price=0.0,
            status=EnrollmentStatus.PENDENTE,
        )
        db.add(legacy)
        await db.commit()
        await db.refresh(legacy)
        legacy_id = legacy.id

    current_user = {
        "user_id": str(user_id),
        "role": "student",
        "tenant_id": str(WR_TENANT_ID),
    }
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        result = await purchase_enrollment(
            EnrollmentPurchaseRequest(course_id=course_id),
            db,
            current_user,
        )

    assert result.enrollment.id == legacy_id
    assert result.enrollment.status == EnrollmentStatus.CONFIRMADA
    assert result.payment is None
