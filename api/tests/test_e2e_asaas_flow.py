"""E2E mocked Asaas flow — full payment lifecycle.

Tests the complete flow:
1. Admin connects Asaas (mock mode)
2. Student purchases a course
3. Checkout creates an Asaas charge
4. Webhook confirms payment
5. Enrollment is unlocked
6. Duplicate webhook is idempotent
"""

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
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole


async def _setup_course_and_student():
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))

        admin = User(
            email=f"e2e_admin_{uuid.uuid4().hex[:6]}@wr.test",
            full_name="E2E Admin",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)
        await db.flush()

        student_user = User(
            email=f"e2e_stu_{uuid.uuid4().hex[:6]}@wr.test",
            full_name="E2E Student",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(student_user)
        await db.flush()

        student = Student(
            user_id=student_user.id,
            tenant_id=WR_TENANT_ID,
            cpf=str(uuid.uuid4().int)[:11],
            phone="11999999999",
        )
        db.add(student)
        await db.flush()

        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"E2E-{uuid.uuid4().hex[:6].upper()}",
            name="E2E Test Course",
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=150.0,
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

        await db.commit()
        return {
            "admin_id": admin.id,
            "student_user_id": student_user.id,
            "student_id": student.id,
            "course_id": course.id,
            "class_id": cls.id,
        }


def _headers(user_id, role, tenant_id=WR_TENANT_ID):
    token = create_access_token(
        {"sub": str(user_id), "role": role, "tenant_id": str(tenant_id)}
    )
    return {"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"}


@pytest.mark.asyncio
async def test_e2e_asaas_full_lifecycle(client, monkeypatch):
    """Full E2E: connect → purchase → checkout → webhook → unlock → idempotent."""
    ctx = await _setup_course_and_student()

    # Enable mock mode for both Asaas and MP
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    admin_headers = _headers(ctx["admin_id"], "admin")
    student_headers = _headers(ctx["student_user_id"], "student")

    # ── Step 1: Admin connects Asaas ──
    connect_resp = await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_asaas_key_12345678901234567890"},
        headers=admin_headers,
    )
    assert connect_resp.status_code == 200
    assert connect_resp.json()["status"] == "connected"

    # Verify status
    status_resp = await client.get(
        "/api/v1/integrations/asaas/status",
        headers=admin_headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["configured"] is True
    assert status_resp.json()["active_provider"] == "ASAAS"

    # ── Step 2: Student purchases the course ──
    purchase_resp = await client.post(
        "/api/v1/enrollments/purchase",
        json={
            "course_id": str(ctx["course_id"]),
            "method": "UNDEFINED",
        },
        headers=student_headers,
    )
    assert purchase_resp.status_code == 201
    purchase_data = purchase_resp.json()
    payment_id = purchase_data["payment"]["id"]
    enrollment_id = purchase_data["enrollment"]["id"]

    # ── Step 3: Student creates checkout (Asaas charge) ──
    checkout_resp = await client.post(
        f"/api/v1/payments/{payment_id}/checkout",
        headers=student_headers,
    )
    assert checkout_resp.status_code == 200
    checkout_data = checkout_resp.json()
    assert "checkout_url" in checkout_data
    assert "preference_id" in checkout_data

    # Verify payment has provider=ASAAS and provider_payment_id set
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = await db.get(Payment, uuid.UUID(payment_id))
        assert payment.provider == PaymentProvider.ASAAS
        assert payment.provider_payment_id is not None
        assert payment.checkout_url is not None
        assert payment.status == PaymentStatus.PROCESSANDO
        provider_payment_id = payment.provider_payment_id

    # ── Step 4: Asaas webhook confirms payment ──
    # Get the webhook token
    from app.services.tenant_secret_service import get_tenant_secret
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        webhook_token = await get_tenant_secret(db, WR_TENANT_ID, "asaas_webhook_token")

    event_id = f"evt_e2e_{uuid.uuid4().hex[:8]}"
    webhook_resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": event_id,
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": provider_payment_id},
        },
        headers={"asaas-access-token": webhook_token},
    )
    assert webhook_resp.status_code == 200
    assert webhook_resp.json()["status"] == "ok"
    assert webhook_resp.json()["payment_status"] == "APROVADO"

    # ── Step 5: Verify enrollment is unlocked ──
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        enrollment = await db.get(Enrollment, uuid.UUID(enrollment_id))
        assert enrollment.status == EnrollmentStatus.CONFIRMADA

        payment = await db.get(Payment, uuid.UUID(payment_id))
        assert payment.status == PaymentStatus.APROVADO
        assert payment.paid_at is not None

    # ── Step 6: Duplicate webhook is idempotent ──
    dup_resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": event_id,
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": provider_payment_id},
        },
        headers={"asaas-access-token": webhook_token},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["duplicate"] is True

    # Verify enrollment still CONFIRMADA (not re-processed)
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        enrollment = await db.get(Enrollment, uuid.UUID(enrollment_id))
        assert enrollment.status == EnrollmentStatus.CONFIRMADA


@pytest.mark.asyncio
async def test_e2e_asaas_checkout_idempotency(client, monkeypatch):
    """E2E: double checkout with Asaas reuses the existing charge."""
    ctx = await _setup_course_and_student()

    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    admin_headers = _headers(ctx["admin_id"], "admin")
    student_headers = _headers(ctx["student_user_id"], "student")

    # Connect Asaas
    await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_asaas_key_12345678901234567890"},
        headers=admin_headers,
    )

    # Purchase
    purchase_resp = await client.post(
        "/api/v1/enrollments/purchase",
        json={"course_id": str(ctx["course_id"]), "method": "UNDEFINED"},
        headers=student_headers,
    )
    payment_id = purchase_resp.json()["payment"]["id"]

    # First checkout
    resp1 = await client.post(
        f"/api/v1/payments/{payment_id}/checkout",
        headers=student_headers,
    )
    assert resp1.status_code == 200
    first_pid = resp1.json()["preference_id"]
    assert resp1.json().get("reused") is not True

    # Second checkout — should reuse
    resp2 = await client.post(
        f"/api/v1/payments/{payment_id}/checkout",
        headers=student_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["preference_id"] == first_pid
    assert resp2.json()["reused"] is True
