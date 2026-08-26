import uuid
from datetime import timedelta

import pytest

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.class_model import Class, ClassStatus
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.financial_lifecycle import (
    expire_abandoned_internal_attempt,
    reconcile_special_financial_event,
)


async def _seed_financial_case(
    *,
    enrollment_status: EnrollmentStatus = EnrollmentStatus.CONFIRMADA,
    payment_status: PaymentStatus = PaymentStatus.APROVADO,
    with_certificate: bool = False,
):
    today = utc_now().date()
    async with AsyncSessionLocal() as db:
        admin = User(
            tenant_id=WR_TENANT_ID,
            email=f"financial-admin-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Admin Financeiro",
            cpf=str(uuid.uuid4().int)[-11:],
            password_hash=hash_password("admin123"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        user = User(
            tenant_id=WR_TENANT_ID,
            email=f"financial-student-{uuid.uuid4().hex[:8]}@example.com",
            full_name="Aluno Financeiro",
            cpf=str(uuid.uuid4().int)[-11:],
            password_hash=hash_password("student123"),
            role=UserRole.STUDENT,
            is_active=True,
        )
        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"FIN-{uuid.uuid4().hex[:6].upper()}",
            name="Curso Financeiro",
            category="Segurança",
            carga_horaria=8,
            modality="EAD",
            price=120.0,
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
            price=120.0,
            status=enrollment_status,
        )
        db.add(enrollment)
        await db.flush()

        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment.id,
            amount=120.0,
            method=PaymentMethod.PIX,
            status=payment_status,
            paid_at=utc_now() if payment_status == PaymentStatus.APROVADO else None,
        )
        db.add(payment)
        await db.flush()

        certificate_id = None
        if with_certificate:
            certificate = Certificate(
                tenant_id=WR_TENANT_ID,
                enrollment_id=enrollment.id,
                certificate_number=f"CERT-{uuid.uuid4().hex}",
                validation_code=uuid.uuid4().hex,
            )
            db.add(certificate)
            await db.flush()
            certificate_id = certificate.id

        await db.commit()
        return payment.id, enrollment.id, certificate_id


def test_stale_providerless_pending_attempt_expires(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENT_PENDING_ATTEMPT_TTL_MINUTES", 30)
    payment = Payment(
        tenant_id=WR_TENANT_ID,
        enrollment_id=uuid.uuid4(),
        amount=100.0,
        method=PaymentMethod.PIX,
        status=PaymentStatus.PENDENTE,
        created_at=utc_now() - timedelta(minutes=31),
    )

    assert expire_abandoned_internal_attempt(payment) is True
    assert payment.status == PaymentStatus.EXPIRADO


def test_attempt_with_external_charge_never_expires_locally(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENT_PENDING_ATTEMPT_TTL_MINUTES", 30)
    payment = Payment(
        tenant_id=WR_TENANT_ID,
        enrollment_id=uuid.uuid4(),
        amount=100.0,
        method=PaymentMethod.BOLETO,
        status=PaymentStatus.PENDENTE,
        provider_payment_id="pay_external_123",
        checkout_url="https://payments.example/123",
        created_at=utc_now() - timedelta(days=2),
    )

    assert expire_abandoned_internal_attempt(payment) is False
    assert payment.status == PaymentStatus.PENDENTE


@pytest.mark.asyncio
async def test_full_refund_before_completion_revokes_access():
    payment_id, enrollment_id, _ = await _seed_financial_case()

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await reconcile_special_financial_event(
            db,
            payment,
            enrollment,
            "PAYMENT_REFUNDED",
        )
        await db.commit()

    assert result["access_revoked"] is True
    assert result["review_required"] is False

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        enrollment = await db.get(Enrollment, enrollment_id)
        assert payment.status == PaymentStatus.REEMBOLSADO
        assert enrollment.status == EnrollmentStatus.CANCELADA


@pytest.mark.asyncio
async def test_refund_after_certificate_preserves_history_and_requires_review():
    payment_id, enrollment_id, certificate_id = await _seed_financial_case(
        enrollment_status=EnrollmentStatus.CONCLUIDA,
        with_certificate=True,
    )

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await reconcile_special_financial_event(
            db,
            payment,
            enrollment,
            "PAYMENT_REFUNDED",
        )
        await db.commit()

    assert result["access_revoked"] is False
    assert result["review_required"] is True
    assert result["review_reason"] == "refund_after_completion_or_certificate"

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        enrollment = await db.get(Enrollment, enrollment_id)
        certificate = await db.get(Certificate, certificate_id)
        assert payment.status == PaymentStatus.REEMBOLSADO
        assert enrollment.status == EnrollmentStatus.CONCLUIDA
        assert certificate is not None


@pytest.mark.asyncio
async def test_chargeback_dispute_flags_review_without_revoking_access():
    payment_id, enrollment_id, _ = await _seed_financial_case()

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        enrollment = await db.get(Enrollment, enrollment_id)
        result = await reconcile_special_financial_event(
            db,
            payment,
            enrollment,
            "PAYMENT_CHARGEBACK_REQUESTED",
        )
        await db.commit()

    assert result["access_revoked"] is False
    assert result["review_required"] is True

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        enrollment = await db.get(Enrollment, enrollment_id)
        assert payment.status == PaymentStatus.APROVADO
        assert payment.review_required is True
        assert enrollment.status == EnrollmentStatus.CONFIRMADA


@pytest.mark.asyncio
async def test_mercado_pago_dispute_won_clears_review_and_keeps_access():
    payment_id, enrollment_id, _ = await _seed_financial_case()

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        enrollment = await db.get(Enrollment, enrollment_id)
        await reconcile_special_financial_event(
            db,
            payment,
            enrollment,
            "MERCADO_PAGO_CHARGEBACK_IN_PROCESS",
        )
        await reconcile_special_financial_event(
            db,
            payment,
            enrollment,
            "MERCADO_PAGO_CHARGEBACK_REIMBURSED",
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        enrollment = await db.get(Enrollment, enrollment_id)
        assert payment.status == PaymentStatus.APROVADO
        assert payment.review_required is False
        assert payment.review_reason is None
        assert enrollment.status == EnrollmentStatus.CONFIRMADA
