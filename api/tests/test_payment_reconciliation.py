"""Tests for shared payment reconciliation and demo payment endpoints.

Verifies:
- Webhook and demo simulator use the same reconciliation core
- Amount mismatch on approve does NOT confirm enrollment
- Repeated approve is idempotent
- Reject sets correct status
- Pending sets correct status
- Demo payment authorization: owner OK, other student 403, admin OK
- Checkout redirects to /demo/payment/<id> in mock mode
- Demo payment GET returns course_id
"""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.class_model import Class, ClassStatus
from app.models.course import Course, CourseModality, CourseType
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.payment_reconciliation import reconcile_payment_status


async def _set_rls_bypass(db):
    await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
    await db.execute(text("SET LOCAL app.bypass_rls = '1'"))


async def _create_student_with_payment(email, course_price=299.90, payment_amount=None):
    """Create a student, course, class, enrollment, and payment. Return IDs."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)

        user = User(
            email=email,
            full_name=f"Student {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(user)
        await db.flush()

        student = Student(user_id=user.id, tenant_id=WR_TENANT_ID, cpf=str(uuid.uuid4().int)[:11])
        db.add(student)
        await db.flush()

        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"TEST-{uuid.uuid4().hex[:6]}",
            name="Test Course",
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=course_price,
        )
        db.add(course)
        await db.flush()

        cls = Class(
            tenant_id=WR_TENANT_ID,
            course_id=course.id,
            responsible_admin_id=user.id,
            start_date=__import__("datetime").date.today(),
            end_date=__import__("datetime").date.today(),
            max_students=50,
            location="TEST",
            status=ClassStatus.ABERTA,
        )
        db.add(cls)
        await db.flush()

        enrollment = Enrollment(
            tenant_id=WR_TENANT_ID,
            student_id=student.id,
            class_id=cls.id,
            status=EnrollmentStatus.PENDENTE,
            price=course_price,
        )
        db.add(enrollment)
        await db.flush()

        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment.id,
            amount=payment_amount or course_price,
            status=PaymentStatus.PENDENTE,
            method=PaymentMethod.PIX,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        await db.refresh(enrollment)
        await db.refresh(course)
        return {
            "user_id": user.id,
            "payment_id": payment.id,
            "enrollment_id": enrollment.id,
            "course_id": course.id,
        }


@pytest.mark.asyncio
async def test_reconcile_approve_confirms_enrollment():
    """Approve with matching amount confirms enrollment."""
    ids = await _create_student_with_payment("recon1@wr.test")

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        payment = await db.get(Payment, ids["payment_id"])
        enrollment = await db.get(Enrollment, ids["enrollment_id"])

        result = await reconcile_payment_status(payment, enrollment, PaymentStatus.APROVADO)
        await db.commit()

        assert result["payment_status"] == "APROVADO"
        assert result["enrollment_confirmed"] is True
        assert result["amount_match"] is True
        assert enrollment.status == EnrollmentStatus.CONFIRMADA
        assert payment.paid_at is not None


@pytest.mark.asyncio
async def test_reconcile_approve_amount_mismatch_no_confirm():
    """Approve with mismatched amount does NOT confirm enrollment."""
    ids = await _create_student_with_payment("recon2@wr.test", course_price=299.90, payment_amount=1.00)

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        payment = await db.get(Payment, ids["payment_id"])
        enrollment = await db.get(Enrollment, ids["enrollment_id"])

        result = await reconcile_payment_status(payment, enrollment, PaymentStatus.APROVADO)
        await db.commit()

        assert result["payment_status"] == "APROVADO"
        assert result["amount_match"] is False
        assert result["enrollment_confirmed"] is False
        assert enrollment.status != EnrollmentStatus.CONFIRMADA


@pytest.mark.asyncio
async def test_reconcile_approve_idempotent():
    """Repeated approve is idempotent."""
    ids = await _create_student_with_payment("recon3@wr.test")

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        payment = await db.get(Payment, ids["payment_id"])
        enrollment = await db.get(Enrollment, ids["enrollment_id"])

        # First approve
        await reconcile_payment_status(payment, enrollment, PaymentStatus.APROVADO)
        await db.commit()

        # Second approve — should be idempotent
        result = await reconcile_payment_status(payment, enrollment, PaymentStatus.APROVADO)
        await db.commit()

        assert result["idempotent"] is True
        assert result["enrollment_confirmed"] is True


@pytest.mark.asyncio
async def test_reconcile_reject_sets_status():
    """Reject sets payment status to RECUSADO."""
    ids = await _create_student_with_payment("recon4@wr.test")

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        payment = await db.get(Payment, ids["payment_id"])
        enrollment = await db.get(Enrollment, ids["enrollment_id"])

        result = await reconcile_payment_status(payment, enrollment, PaymentStatus.RECUSADO)
        await db.commit()

        assert result["payment_status"] == "RECUSADO"
        assert payment.status == PaymentStatus.RECUSADO


@pytest.mark.asyncio
async def test_reconcile_pending_sets_status():
    """Pending sets payment status to PROCESSANDO."""
    ids = await _create_student_with_payment("recon5@wr.test")

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        payment = await db.get(Payment, ids["payment_id"])
        enrollment = await db.get(Enrollment, ids["enrollment_id"])

        result = await reconcile_payment_status(payment, enrollment, PaymentStatus.PROCESSANDO)
        await db.commit()

        assert result["payment_status"] == "PROCESSANDO"
        assert payment.status == PaymentStatus.PROCESSANDO


@pytest.mark.asyncio
async def test_demo_payment_get_returns_course_id(client, monkeypatch):
    """Demo payment GET returns course_id in response."""
    
    monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", True)

    ids = await _create_student_with_payment("demoget1@wr.test")
    token = create_access_token(
        {"sub": str(ids["user_id"]), "role": "student", "tenant_id": str(WR_TENANT_ID)}
    )

    resp = await client.get(
        f"/api/v1/payments/demo/{ids['payment_id']}",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["course_id"] == str(ids["course_id"])
    assert body["course_name"] == "Test Course"


@pytest.mark.asyncio
async def test_demo_payment_owner_can_approve(client, monkeypatch):
    """Owner student can approve their own payment."""
    
    monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", True)

    ids = await _create_student_with_payment("demoown1@wr.test")
    token = create_access_token(
        {"sub": str(ids["user_id"]), "role": "student", "tenant_id": str(WR_TENANT_ID)}
    )

    resp = await client.post(
        f"/api/v1/payments/demo/{ids['payment_id']}/approve",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_status"] == "APROVADO"
    assert body["enrollment_confirmed"] is True


@pytest.mark.asyncio
async def test_demo_payment_other_student_forbidden(client, monkeypatch):
    """A different student in the same tenant gets 403."""
    
    monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", True)

    ids = await _create_student_with_payment("demoother1@wr.test")
    # Create a second student
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        user2 = User(
            email="demoother2@wr.test",
            full_name="Other Student",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(user2)
        await db.commit()
        user2_id = user2.id

    token = create_access_token(
        {"sub": str(user2_id), "role": "student", "tenant_id": str(WR_TENANT_ID)}
    )

    resp = await client.post(
        f"/api/v1/payments/demo/{ids['payment_id']}/approve",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_demo_payment_admin_can_approve(client, monkeypatch):
    """Admin of the same tenant can approve any payment."""
    
    monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", True)

    ids = await _create_student_with_payment("demoadmin1@wr.test")
    # Create an admin
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        admin = User(
            email="demoadmin2@wr.test",
            full_name="Admin",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)
        await db.commit()
        admin_id = admin.id

    token = create_access_token(
        {"sub": str(admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
    )

    resp = await client.post(
        f"/api/v1/payments/demo/{ids['payment_id']}/approve",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_checkout_mock_mode_redirects_to_demo_page(client, monkeypatch):
    """In mock mode, checkout returns a RELATIVE /demo/payment/<id> URL.

    The URL must NOT contain FRONTEND_URL so the browser stays on whichever
    tenant frontend origin it is currently using (WR Vercel or Alfa Vercel).
    """

    monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", True)
    monkeypatch.setattr("app.core.config.settings.FRONTEND_URL", "https://wr.vercel.app")

    ids = await _create_student_with_payment("democheckout1@wr.test")
    token = create_access_token(
        {"sub": str(ids["user_id"]), "role": "student", "tenant_id": str(WR_TENANT_ID)}
    )

    resp = await client.post(
        f"/api/v1/payments/{ids['payment_id']}/checkout",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "/demo/payment/" in body["checkout_url"]
    assert str(ids["payment_id"]) in body["checkout_url"]
    assert "mock-mp.test" not in body["checkout_url"]
    # Relative URL — must NOT contain FRONTEND_URL or any scheme/host
    assert "https://" not in body["checkout_url"]
    assert "http://" not in body["checkout_url"]
    assert body["checkout_url"].startswith("/demo/payment/")


@pytest.mark.asyncio
async def test_demo_payment_amount_mismatch_no_confirm(client, monkeypatch):
    """Demo approve with amount mismatch does NOT confirm enrollment."""
    
    monkeypatch.setattr("app.core.config.settings.MERCADO_PAGO_MOCK_MODE", True)

    ids = await _create_student_with_payment(
        "demomismatch@wr.test", course_price=299.90, payment_amount=1.00
    )
    token = create_access_token(
        {"sub": str(ids["user_id"]), "role": "student", "tenant_id": str(WR_TENANT_ID)}
    )

    resp = await client.post(
        f"/api/v1/payments/demo/{ids['payment_id']}/approve",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_status"] == "APROVADO"
    assert body["amount_match"] is False
    assert body["enrollment_confirmed"] is False
