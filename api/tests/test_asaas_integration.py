"""Tests for Asaas integration management and webhook endpoint."""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.payment import (
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    PaymentWebhookEvent,
)
from app.models.tenant_secret import TenantSecret
from app.models.user import User, UserRole
from app.services.tenant_secret_service import (
    ASAAS_API_KEY_KEY,
    set_tenant_secret,
)


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


# ─── Status ───

@pytest.mark.asyncio
async def test_asaas_status_not_configured(client):
    """Status returns not configured when no API key is stored."""
    admin_id = await _create_admin("asaas_status@wr.test", WR_TENANT_ID)
    resp = await client.get(
        "/api/v1/integrations/asaas/status",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["configured"] is False
    assert resp.json()["webhook_configured"] is False
    assert resp.json()["active_provider"] == "MERCADO_PAGO"


@pytest.mark.asyncio
async def test_asaas_status_configured(client):
    """Status returns configured when API key and webhook token exist."""
    admin_id = await _create_admin("asaas_status2@wr.test", WR_TENANT_ID)

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        await set_tenant_secret(db, WR_TENANT_ID, ASAAS_API_KEY_KEY, "fake_key_12345678901234567890")
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_webhook_token", "webhook_tok_123")
        await db.commit()

    resp = await client.get(
        "/api/v1/integrations/asaas/status",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["configured"] is True
    assert resp.json()["webhook_configured"] is True


# ─── Connect (mock mode) ───

@pytest.mark.asyncio
async def test_asaas_connect_mock_mode(client, monkeypatch):
    """Connect stores API key and webhook token in mock mode."""
    admin_id = await _create_admin("asaas_connect@wr.test", WR_TENANT_ID)

    # Enable mock mode to skip real API validation
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    resp = await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_asaas_key_12345678901234567890"},
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"

    # Verify credentials were stored
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        secrets = (await db.execute(
            select(TenantSecret).where(TenantSecret.tenant_id == WR_TENANT_ID)
        )).scalars().all()
        keys = {s.key for s in secrets}
        assert "asaas_api_key" in keys
        assert "asaas_webhook_token" in keys


@pytest.mark.asyncio
async def test_asaas_connect_invalid_key_format(client, monkeypatch):
    """Connect rejects too-short API keys."""
    admin_id = await _create_admin("asaas_connect_bad@wr.test", WR_TENANT_ID)

    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    resp = await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "short"},
        headers=_headers(admin_id),
    )
    assert resp.status_code == 400


# ─── Disconnect ───

@pytest.mark.asyncio
async def test_asaas_disconnect(client, monkeypatch):
    """Disconnect removes stored credentials."""
    admin_id = await _create_admin("asaas_disc@wr.test", WR_TENANT_ID)

    # First connect
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)
    await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_asaas_key_12345678901234567890"},
        headers=_headers(admin_id),
    )

    # Then disconnect
    resp = await client.delete(
        "/api/v1/integrations/asaas/",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"

    # Verify credentials were removed
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        secrets = (await db.execute(
            select(TenantSecret).where(
                TenantSecret.tenant_id == WR_TENANT_ID,
                TenantSecret.key.in_(["asaas_api_key", "asaas_webhook_token"]),
            )
        )).scalars().all()
        assert len(secrets) == 0


# ─── Webhook endpoint ───

async def _setup_asaas_webhook_tenant(tenant_slug="wr"):
    """Set up a tenant with Asaas webhook token and return the token."""
    webhook_token = "test_webhook_token_abc123"
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_webhook_token", webhook_token)
        await db.commit()
    return webhook_token


async def _create_asaas_payment(amount=299.90, enrollment_id=None):
    """Create an Asaas payment in the DB for webhook testing."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment_id,
            amount=amount,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
            provider=PaymentProvider.ASAAS,
            provider_payment_id=f"pay_test_{uuid.uuid4().hex[:8]}",
            checkout_url="https://asaas.test/checkout",
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        return payment.id, payment.provider_payment_id


@pytest.mark.asyncio
async def test_webhook_missing_token_rejected(client):
    """Webhook without access token → 403."""
    await _setup_asaas_webhook_tenant()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={"id": "evt_1", "event": "PAYMENT_RECEIVED", "payment": {"id": "pay_1"}},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_wrong_token_rejected(client):
    """Webhook with wrong token → 403."""
    await _setup_asaas_webhook_tenant()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={"id": "evt_1", "event": "PAYMENT_RECEIVED", "payment": {"id": "pay_1"}},
        headers={"asaas-access-token": "wrong_token"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_correct_token_accepted(client):
    """Webhook with correct token processes the event."""
    token = await _setup_asaas_webhook_tenant()
    _payment_id, provider_pid = await _create_asaas_payment()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["payment_status"] == "APROVADO"


@pytest.mark.asyncio
async def test_webhook_duplicate_event_idempotent(client):
    """Duplicate webhook event does not re-apply transition."""
    token = await _setup_asaas_webhook_tenant()
    _payment_id, provider_pid = await _create_asaas_payment()

    event_id = f"evt_dup_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": event_id,
        "event": "PAYMENT_RECEIVED",
        "payment": {"id": provider_pid},
    }

    # First event
    resp1 = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json=payload,
        headers={"asaas-access-token": token},
    )
    assert resp1.status_code == 200
    assert resp1.json().get("duplicate") is not True

    # Duplicate event
    resp2 = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json=payload,
        headers={"asaas-access-token": token},
    )
    assert resp2.status_code == 200
    assert resp2.json()["duplicate"] is True

    # Verify only one webhook event record
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        events = (await db.execute(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider_event_id == event_id
            )
        )).scalars().all()
        assert len(events) == 1


@pytest.mark.asyncio
async def test_webhook_unknown_event_does_not_crash(client):
    """Unknown event type is recorded but doesn't crash the webhook."""
    token = await _setup_asaas_webhook_tenant()
    _payment_id, provider_pid = await _create_asaas_payment()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_unknown_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_SOME_FUTURE_EVENT",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["unknown_event"] is True


@pytest.mark.asyncio
async def test_webhook_cross_tenant_denied(client):
    """WR webhook token cannot authenticate an Alfa webhook call.

    The webhook is sent to /webhook/wr but the payment belongs to Alfa.
    The payment should not be found because we query by the resolved
    tenant (WR), not the payload's tenant.
    """
    from app.models.tenant import Tenant, TenantStatus

    # Create Alfa tenant
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        alfa = Tenant(
            name="Alfa",
            slug="alfa",
            status=TenantStatus.ACTIVE,
            contact_name="Alfa",
            contact_email="alfa@test",
        )
        db.add(alfa)
        await db.commit()
        await db.refresh(alfa)
        alfa_id = alfa.id

    # Create a payment in Alfa tenant
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        alfa_payment = Payment(
            tenant_id=alfa_id,
            amount=100.0,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
            provider=PaymentProvider.ASAAS,
            provider_payment_id="pay_alfa_123",
        )
        db.add(alfa_payment)
        await db.commit()

    # Set up WR webhook token
    token = await _setup_asaas_webhook_tenant()

    # Send webhook to WR endpoint but with Alfa's payment id
    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_cross_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": "pay_alfa_123"},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_found"] is False

    # Verify Alfa payment was NOT modified
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        p = (await db.execute(
            select(Payment).where(Payment.provider_payment_id == "pay_alfa_123")
        )).scalar_one()
        assert p.status == PaymentStatus.PROCESSANDO  # unchanged
