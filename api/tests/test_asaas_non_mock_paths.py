"""Tests for Asaas integration non-mock paths (connect, validate, disconnect, webhook)."""

import uuid
from unittest.mock import AsyncMock, patch

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
)
from app.models.tenant import Tenant
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


async def _setup_asaas_tenant():
    """Set up tenant with Asaas API key and webhook metadata."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_api_key", "fake_key_12345678901234567890")
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_webhook_token", "x" * 43)
        tenant = (await db.execute(
            __import__("sqlalchemy").select(Tenant).where(Tenant.id == WR_TENANT_ID)
        )).scalar_one()
        ts = dict(tenant.settings or {})
        ts["payment_provider"] = "ASAAS"
        ts["asaas_webhook_id"] = "wh_test_123"
        ts["asaas_webhook_enabled"] = True
        ts["asaas_webhook_interrupted"] = False
        tenant.settings = ts
        await db.commit()


@pytest.mark.asyncio
async def test_validate_non_mock_healthy(client, monkeypatch):
    """Validate in non-mock mode checks webhook health via API."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    admin_id = await _create_admin("asaas_val_real@wr.test", WR_TENANT_ID)
    await _setup_asaas_tenant()

    # Mock the AsaasProvider to return a healthy webhook
    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import WebhookConfig

    mock_wh = WebhookConfig(
        id="wh_test_123",
        name="WR Cursos Payments - wr",
        url="https://api.test/webhook/wr",
        enabled=True,
        interrupted=False,
        events=["PAYMENT_RECEIVED"],
    )

    with patch.object(AsaasProvider, "get_webhook", return_value=mock_wh), \
         patch.object(AsaasProvider, "_request", return_value={"data": [], "totalCount": 0}):
        resp = await client.post(
            "/api/v1/integrations/asaas/validate",
            headers=_headers(admin_id),
        )

    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["webhook_healthy"] is True


@pytest.mark.asyncio
async def test_validate_non_mock_unhealthy(client, monkeypatch):
    """Validate in non-mock mode detects unhealthy webhook."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    admin_id = await _create_admin("asaas_val_unhealthy@wr.test", WR_TENANT_ID)
    await _setup_asaas_tenant()

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import WebhookConfig

    mock_wh = WebhookConfig(
        id="wh_test_123",
        name="WR Cursos Payments - wr",
        url="https://api.test/webhook/wr",
        enabled=False,
        interrupted=True,
        events=["PAYMENT_RECEIVED"],
    )

    with patch.object(AsaasProvider, "get_webhook", return_value=mock_wh), \
         patch.object(AsaasProvider, "_request", return_value={"data": [], "totalCount": 0}):
        resp = await client.post(
            "/api/v1/integrations/asaas/validate",
            headers=_headers(admin_id),
        )

    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["webhook_healthy"] is False


@pytest.mark.asyncio
async def test_disconnect_non_mock_disables_webhook(client, monkeypatch):
    """Disconnect in non-mock mode disables the remote webhook."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    admin_id = await _create_admin("asaas_disc_real@wr.test", WR_TENANT_ID)
    await _setup_asaas_tenant()

    from app.services.asaas_provider import AsaasProvider

    with patch.object(AsaasProvider, "update_webhook", new_callable=AsyncMock), \
         patch.object(AsaasProvider, "delete_webhook", new_callable=AsyncMock):
        resp = await client.delete(
            "/api/v1/integrations/asaas/",
            headers=_headers(admin_id),
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"

    # Verify webhook metadata was cleared
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        tenant = (await db.execute(select(Tenant).where(Tenant.id == WR_TENANT_ID))).scalar_one()
        ts = tenant.settings or {}
        assert "asaas_webhook_id" not in ts
        assert "payment_provider" not in ts


@pytest.mark.asyncio
async def test_connect_non_mock_reconciles_webhook(client, monkeypatch):
    """Connect in non-mock mode reconciles the webhook via API."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    admin_id = await _create_admin("asaas_connect_real@wr.test", WR_TENANT_ID)

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import WebhookConfig

    WebhookConfig(
        id="wh_new_123",
        name="WR Cursos Payments - wr",
        url="https://api.test/webhook/wr",
        enabled=True,
        interrupted=False,
        events=["PAYMENT_RECEIVED"],
    )

    # Mock _request to return valid responses for customer lookup and webhook creation
    def mock_request(method, path, **kwargs):
        if method == "GET" and path == "/v3/customers":
            return {"data": [], "totalCount": 0}
        if method == "POST" and path == "/v3/webhooks":
            return {
                "id": "wh_new_123",
                "name": "WR Cursos Payments - wr",
                "url": "https://api.test/webhook/wr",
                "enabled": True,
                "interrupted": False,
                "event": {"paymentReceived": True},
            }
        if method == "GET" and path.startswith("/v3/webhooks"):
            return {"data": [], "totalCount": 0}
        return {}

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        resp = await client.post(
            "/api/v1/integrations/asaas/connect",
            json={"api_key": "fake_asaas_key_12345678901234567890"},
            headers=_headers(admin_id),
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"
    assert resp.json()["webhook_configured"] is True


@pytest.mark.asyncio
async def test_webhook_identity_verification_external_ref_mismatch(client, monkeypatch):
    """Webhook identity verification detects externalReference mismatch."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    await _create_admin("asaas_id_mismatch@wr.test", WR_TENANT_ID)
    await _setup_asaas_tenant()

    # Create a payment
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = Payment(
            tenant_id=WR_TENANT_ID,
            amount=299.90,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
            provider=PaymentProvider.ASAAS,
            provider_payment_id="pay_test_mismatch",
            checkout_url="https://asaas.test/checkout",
        )
        db.add(payment)
        await db.commit()

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentInfoResult

    # Mock get_payment_info to return a mismatched externalReference
    mock_info = PaymentInfoResult(
        provider_payment_id="pay_test_mismatch",
        status="RECEIVED",
        amount=299.90,
        billing_type="PIX",
        customer_id="cus_test",
        external_reference="wrong-payment-id",
    )

    with patch.object(AsaasProvider, "get_payment_info", return_value=mock_info):
        resp = await client.post(
            "/api/v1/integrations/asaas/webhook/wr",
            json={
                "id": f"evt_mismatch_{uuid.uuid4().hex[:8]}",
                "event": "PAYMENT_RECEIVED",
                "payment": {"id": "pay_test_mismatch"},
            },
            headers={"asaas-access-token": "x" * 43},
        )

    assert resp.status_code == 200
    assert resp.json()["state"] == "FAILED"
    assert resp.json()["reason"] == "external_reference_mismatch"


@pytest.mark.asyncio
async def test_webhook_identity_verification_amount_mismatch(client, monkeypatch):
    """Webhook identity verification detects amount mismatch."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    await _create_admin("asaas_amt_mismatch@wr.test", WR_TENANT_ID)
    await _setup_asaas_tenant()

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = Payment(
            tenant_id=WR_TENANT_ID,
            amount=299.90,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
            provider=PaymentProvider.ASAAS,
            provider_payment_id="pay_test_amt",
            checkout_url="https://asaas.test/checkout",
        )
        db.add(payment)
        await db.commit()
        payment_id = payment.id

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentInfoResult

    mock_info = PaymentInfoResult(
        provider_payment_id="pay_test_amt",
        status="RECEIVED",
        amount=999.99,  # Wrong amount
        billing_type="PIX",
        customer_id="cus_test",
        external_reference=str(payment_id),
    )

    with patch.object(AsaasProvider, "get_payment_info", return_value=mock_info):
        resp = await client.post(
            "/api/v1/integrations/asaas/webhook/wr",
            json={
                "id": f"evt_amt_{uuid.uuid4().hex[:8]}",
                "event": "PAYMENT_RECEIVED",
                "payment": {"id": "pay_test_amt"},
            },
            headers={"asaas-access-token": "x" * 43},
        )

    assert resp.status_code == 200
    assert resp.json()["state"] == "FAILED"


@pytest.mark.asyncio
async def test_webhook_identity_verification_success(client, monkeypatch):
    """Webhook identity verification succeeds with matching data."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    await _create_admin("asaas_id_ok@wr.test", WR_TENANT_ID)
    await _setup_asaas_tenant()

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = Payment(
            tenant_id=WR_TENANT_ID,
            amount=299.90,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
            provider=PaymentProvider.ASAAS,
            provider_payment_id="pay_test_ok",
            checkout_url="https://asaas.test/checkout",
        )
        db.add(payment)
        await db.commit()
        payment_id = payment.id

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentInfoResult

    mock_info = PaymentInfoResult(
        provider_payment_id="pay_test_ok",
        status="RECEIVED",
        amount=299.90,
        billing_type="PIX",
        customer_id="cus_test",
        external_reference=str(payment_id),
    )

    with patch.object(AsaasProvider, "get_payment_info", return_value=mock_info):
        resp = await client.post(
            "/api/v1/integrations/asaas/webhook/wr",
            json={
                "id": f"evt_ok_{uuid.uuid4().hex[:8]}",
                "event": "PAYMENT_RECEIVED",
                "payment": {"id": "pay_test_ok"},
            },
            headers={"asaas-access-token": "x" * 43},
        )

    assert resp.status_code == 200
    assert resp.json()["state"] == "PROCESSED"
    assert resp.json()["payment_status"] == "APROVADO"
