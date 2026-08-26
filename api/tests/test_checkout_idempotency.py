"""Tests for checkout idempotency and immutable terminal payment attempts."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.core.utils import utc_now
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole


async def _setup_student_and_payment():
    """Create a student, course, enrollment, and pending payment in WR tenant."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))

        user = User(
            email=f"idem_stu_{uuid.uuid4().hex[:6]}@wr.test",
            full_name="Idempotency Student",
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
            phone="11999999999",
        )
        db.add(student)
        await db.flush()

        admin = User(
            email=f"idem_admin_{uuid.uuid4().hex[:6]}@wr.test",
            full_name="Idempotency Admin",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)
        await db.flush()

        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"IDEM-{uuid.uuid4().hex[:6].upper()}",
            name="Idempotency Course",
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=299.90,
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
            max_students=20,
            status=ClassStatus.ABERTA,
        )
        db.add(cls)
        await db.flush()

        enrollment = Enrollment(
            tenant_id=WR_TENANT_ID,
            student_id=student.id,
            class_id=cls.id,
            price=299.90,
            status=EnrollmentStatus.PENDENTE,
            source=EnrollmentSource.INDIVIDUAL,
        )
        db.add(enrollment)
        await db.flush()

        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment.id,
            amount=299.90,
            status=PaymentStatus.PENDENTE,
            method=PaymentMethod.PIX,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        await db.refresh(user)
        return {
            "payment_id": payment.id,
            "user_id": user.id,
            "student_id": student.id,
            "course_id": course.id,
            "enrollment_id": enrollment.id,
        }


def _headers(user_id, role="student", tenant_id=WR_TENANT_ID):
    token = create_access_token(
        {"sub": str(user_id), "role": role, "tenant_id": str(tenant_id)}
    )
    return {"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"}


@pytest.mark.asyncio
async def test_payment_get_includes_course_context_for_return_journey(client):
    """PaymentReturn receives the real course and enrollment context from API."""
    ctx = await _setup_student_and_payment()

    resp = await client.get(
        f"/api/v1/payments/{ctx['payment_id']}",
        headers=_headers(ctx["user_id"]),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["course_id"] == str(ctx["course_id"])
    assert body["enrollment_status"] == EnrollmentStatus.PENDENTE.value


@pytest.mark.asyncio
async def test_double_checkout_reuses_existing_charge(client, monkeypatch):
    """Calling checkout twice must NOT create a second external charge."""
    ctx = await _setup_student_and_payment()

    call_count = {"n": 0}

    class FakePreference:
        @staticmethod
        async def create_preference(*args, **kwargs):
            call_count["n"] += 1
            return {
                "id": f"PREF-IDEM-{call_count['n']}",
                "init_point": "https://mp.init/idem",
            }

    monkeypatch.setattr(
        "app.services.mercado_pago_provider.MercadoPagoService",
        FakePreference,
    )

    # First checkout
    resp1 = await client.post(
        f"/api/v1/payments/{ctx['payment_id']}/checkout",
        headers=_headers(ctx["user_id"]),
    )
    assert resp1.status_code == 200
    assert resp1.json()["preference_id"] == "PREF-IDEM-1"
    assert resp1.json().get("reused") is not True

    # Second checkout — should reuse, not create new
    resp2 = await client.post(
        f"/api/v1/payments/{ctx['payment_id']}/checkout",
        headers=_headers(ctx["user_id"]),
    )
    assert resp2.status_code == 200
    assert resp2.json()["preference_id"] == "PREF-IDEM-1"
    assert resp2.json().get("reused") is True

    # Provider was called only once
    assert call_count["n"] == 1


@pytest.mark.asyncio
async def test_checkout_after_approval_is_rejected_and_history_preserved(client, monkeypatch):
    """An approved Payment is terminal and cannot be turned into another charge."""
    ctx = await _setup_student_and_payment()

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = await db.get(Payment, ctx["payment_id"])
        payment.status = PaymentStatus.APROVADO
        payment.provider_payment_id = "OLD-PREF"
        payment.checkout_url = "https://old.checkout"
        await db.commit()

    call_count = {"n": 0}

    class FakePreference:
        @staticmethod
        async def create_preference(*args, **kwargs):
            call_count["n"] += 1
            return {
                "id": f"PREF-NEW-{call_count['n']}",
                "init_point": "https://mp.init/new",
            }

    monkeypatch.setattr(
        "app.services.mercado_pago_provider.MercadoPagoService",
        FakePreference,
    )

    resp = await client.post(
        f"/api/v1/payments/{ctx['payment_id']}/checkout",
        headers=_headers(ctx["user_id"]),
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Payment already approved"
    assert call_count["n"] == 0

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = await db.get(Payment, ctx["payment_id"])
        assert payment.status == PaymentStatus.APROVADO
        assert payment.provider_payment_id == "OLD-PREF"
        assert payment.checkout_url == "https://old.checkout"


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_status", [PaymentStatus.RECUSADO, PaymentStatus.REEMBOLSADO])
async def test_checkout_rejects_closed_attempts(client, terminal_status):
    """Rejected/refunded rows stay immutable; purchase must create a new attempt."""
    ctx = await _setup_student_and_payment()

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = await db.get(Payment, ctx["payment_id"])
        payment.status = terminal_status
        payment.provider_payment_id = "CLOSED-PREF"
        payment.checkout_url = "https://closed.checkout"
        await db.commit()

    resp = await client.post(
        f"/api/v1/payments/{ctx['payment_id']}/checkout",
        headers=_headers(ctx["user_id"]),
    )

    assert resp.status_code == 409
    assert "closed" in resp.json()["detail"].lower()

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = await db.get(Payment, ctx["payment_id"])
        assert payment.status == terminal_status
        assert payment.provider_payment_id == "CLOSED-PREF"
        assert payment.checkout_url == "https://closed.checkout"
