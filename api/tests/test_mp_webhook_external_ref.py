"""Tests for MP webhook with external_reference=payment_id (new format)."""

import uuid
from datetime import date

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.class_model import Class
from app.models.course import Course
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole


async def _create_admin(email, tenant_id):
    async with AsyncSessionLocal() as db:
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


def _headers(user_id, role="admin", tenant_id=WR_TENANT_ID):
    token = create_access_token(
        {"sub": str(user_id), "role": role, "tenant_id": str(tenant_id)}
    )
    return {"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"}


async def _create_full_payment():
    """Create a course, class, student, enrollment, and payment."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))

        # Admin (required as class responsible)
        admin = User(
            email=f"mpwh-admin-{uuid.uuid4().hex[:6]}@wr.test",
            full_name="Admin",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)
        await db.flush()

        # Course
        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"MPWH-{uuid.uuid4().hex[:6]}",
            name="MP Webhook Test Course",
            description="Test",
            category="Test",
            carga_horaria=40,
            price=299.90,
        )
        db.add(course)
        await db.flush()

        # Class
        cls = Class(
            tenant_id=WR_TENANT_ID,
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            max_students=100,
        )
        db.add(cls)
        await db.flush()

        # User + Student
        user = User(
            email=f"mpwh-student-{uuid.uuid4().hex[:6]}@wr.test",
            full_name="Student",
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
            cpf=user.cpf,
            phone="11999999999",
        )
        db.add(student)
        await db.flush()

        # Enrollment
        enrollment = Enrollment(
            tenant_id=WR_TENANT_ID,
            student_id=student.id,
            class_id=cls.id,
            status=EnrollmentStatus.PENDENTE,
            price=299.90,
        )
        db.add(enrollment)
        await db.flush()

        # Payment — mercado_pago_id must match what the mock returns
        # Mock returns preference_id = "mock-pref-{id}" where id is the webhook's id field
        # We'll send id = "mock-mp-payment-{payment_id}", so mock returns "mock-pref-{payment_id}"
        # But payment_id isn't known yet. So we'll use a fixed prefix and update after flush.
        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment.id,
            amount=299.90,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
            mercado_pago_id="mock-pref-PLACEHOLDER",
        )
        db.add(payment)
        await db.flush()
        # Update mercado_pago_id to match what the mock will return
        payment.mercado_pago_id = f"mock-pref-{payment.id}"
        await db.commit()
        await db.refresh(payment)
        await db.refresh(enrollment)

        return {
            "payment_id": payment.id,
            "enrollment_id": enrollment.id,
            "mercado_pago_id": payment.mercado_pago_id,
        }


@pytest.mark.asyncio
async def test_mp_webhook_with_payment_id_as_external_reference(client, monkeypatch):
    """MP webhook accepts external_reference=payment_id (new format)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    ctx = await _create_full_payment()
    await _create_admin("mpwh_admin@wr.test", WR_TENANT_ID)

    # Webhook with external_reference = payment_id (new format)
    resp = await client.post(
        "/api/v1/payments/webhook/mercado-pago",
        json={
            "id": f"mock-mp-payment-{ctx['payment_id']}",
            "status": "approved",
            "external_reference": str(ctx["payment_id"]),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Verify payment is APROVADO
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = await db.get(Payment, ctx["payment_id"])
        assert payment.status == PaymentStatus.APROVADO


@pytest.mark.asyncio
async def test_mp_webhook_with_enrollment_id_backward_compat(client, monkeypatch):
    """MP webhook still accepts external_reference=enrollment_id (old format, backward compat)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    ctx = await _create_full_payment()

    # Update mercado_pago_id to match what the mock will return for enrollment_id
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        payment = (await db.execute(select(Payment).where(Payment.id == ctx["payment_id"]))).scalar_one()
        payment.mercado_pago_id = f"mock-pref-{ctx['enrollment_id']}"
        await db.commit()

    # Webhook with external_reference = enrollment_id (old format)
    resp = await client.post(
        "/api/v1/payments/webhook/mercado-pago",
        json={
            "id": f"mock-mp-payment-{ctx['enrollment_id']}",
            "status": "approved",
            "external_reference": str(ctx["enrollment_id"]),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Verify payment is APROVADO
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = await db.get(Payment, ctx["payment_id"])
        assert payment.status == PaymentStatus.APROVADO


@pytest.mark.asyncio
async def test_mp_webhook_invalid_external_reference(client, monkeypatch):
    """MP webhook rejects invalid external_reference (not a UUID)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    resp = await client.post(
        "/api/v1/payments/webhook/mercado-pago",
        json={
            "id": "mock-mp-payment-123",
            "status": "approved",
            "external_reference": "not-a-uuid",
        },
    )
    assert resp.status_code == 400
    assert "Invalid external reference" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_mp_webhook_missing_external_reference(client, monkeypatch):
    """MP webhook rejects missing external_reference."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    resp = await client.post(
        "/api/v1/payments/webhook/mercado-pago",
        json={
            "id": "mock-mp-payment-123",
            "status": "approved",
            "external_reference": "",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_mp_webhook_payment_not_found(client, monkeypatch):
    """MP webhook returns 404 when payment doesn't exist."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    random_uuid = uuid.uuid4()
    resp = await client.post(
        "/api/v1/payments/webhook/mercado-pago",
        json={
            "id": f"mock-mp-payment-{random_uuid}",
            "status": "approved",
            "external_reference": str(random_uuid),
        },
    )
    assert resp.status_code == 404
