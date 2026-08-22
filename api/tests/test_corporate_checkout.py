"""Tests for corporate checkout flow and Asaas reconciliation."""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.company import Company
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.user import User, UserRole
from app.services.tenant_secret_service import set_tenant_secret


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


async def _create_company_payment(amount=5000.0):
    """Create a company and a consolidated company payment."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))

        company = Company(
            tenant_id=WR_TENANT_ID,
            legal_name=f"Test Company {uuid.uuid4().hex[:6]}",
            cnpj=f"{uuid.uuid4().int % 99999999999999:014d}",
            rh_email="rh@testcompany.com",
            rh_phone="11999999999",
        )
        db.add(company)
        await db.flush()

        payment = Payment(
            tenant_id=WR_TENANT_ID,
            company_id=company.id,
            enrollment_id=None,
            amount=amount,
            status=PaymentStatus.PENDENTE,
            method=PaymentMethod.PIX,
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        await db.refresh(company)

        return {
            "payment_id": payment.id,
            "company_id": company.id,
        }


@pytest.mark.asyncio
async def test_corporate_checkout_asaas_mock(client, monkeypatch):
    """Corporate checkout with Asaas in mock mode creates a charge."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    admin_id = await _create_admin("corp_checkout@wr.test", WR_TENANT_ID)
    ctx = await _create_company_payment()

    # Set up Asaas as the provider
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select

        from app.models.tenant import Tenant
        tenant = (await db.execute(select(Tenant).where(Tenant.id == WR_TENANT_ID))).scalar_one()
        ts = dict(tenant.settings or {})
        ts["payment_provider"] = "ASAAS"
        tenant.settings = ts
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_api_key", "fake_key_12345678901234567890")
        await db.commit()

    resp = await client.post(
        f"/api/v1/payments/{ctx['payment_id']}/checkout",
        json={},
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "checkout_url" in data
    assert "preference_id" in data


@pytest.mark.asyncio
async def test_corporate_checkout_student_forbidden(client, monkeypatch):
    """Corporate checkout is admin-only — students get 403."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    ctx = await _create_company_payment()

    # Create a student
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        student = User(
            email=f"corp-student-{uuid.uuid4().hex[:6]}@wr.test",
            full_name="Student",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(student)
        await db.commit()
        await db.refresh(student)
        student_id = student.id

    resp = await client.post(
        f"/api/v1/payments/{ctx['payment_id']}/checkout",
        json={},
        headers=_headers(student_id, "student"),
    )
    assert resp.status_code == 403
    assert "admin" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_corporate_checkout_not_found(client, monkeypatch):
    """Checkout with non-existent payment returns 404."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    admin_id = await _create_admin("corp_404@wr.test", WR_TENANT_ID)
    random_uuid = uuid.uuid4()

    resp = await client.post(
        f"/api/v1/payments/{random_uuid}/checkout",
        json={},
        headers=_headers(admin_id),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_corporate_checkout_idempotent(client, monkeypatch):
    """Double checkout on a corporate payment reuses the existing charge."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)
    monkeypatch.setattr(settings, "MERCADO_PAGO_MOCK_MODE", True)

    admin_id = await _create_admin("corp_idem@wr.test", WR_TENANT_ID)
    ctx = await _create_company_payment()

    # Set up Asaas as the provider
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select

        from app.models.tenant import Tenant
        tenant = (await db.execute(select(Tenant).where(Tenant.id == WR_TENANT_ID))).scalar_one()
        ts = dict(tenant.settings or {})
        ts["payment_provider"] = "ASAAS"
        tenant.settings = ts
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_api_key", "fake_key_12345678901234567890")
        await db.commit()

    # First checkout
    resp1 = await client.post(
        f"/api/v1/payments/{ctx['payment_id']}/checkout",
        json={},
        headers=_headers(admin_id),
    )
    assert resp1.status_code == 200

    # Second checkout should reuse
    resp2 = await client.post(
        f"/api/v1/payments/{ctx['payment_id']}/checkout",
        json={},
        headers=_headers(admin_id),
    )
    assert resp2.status_code == 200
    assert resp2.json().get("reused") is True
