"""Tests for webhook identity verification and race condition handling."""

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
)
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


async def _setup_webhook_tenant():
    """Set up tenant with webhook token and API key, return token."""
    webhook_token = "test_webhook_token_abc123"
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_webhook_token", webhook_token)
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_api_key", "fake_key_12345678901234567890")
        await db.commit()
    return webhook_token


async def _create_payment(amount=299.90, enrollment_id=None, company_id=None):
    """Create an Asaas payment in the DB."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment_id,
            company_id=company_id,
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


# ─── Webhook event state machine tests ───

@pytest.mark.asyncio
async def test_webhook_payment_not_found_sets_pending_match(client, monkeypatch):
    """When payment is not found, event should be PENDING_MATCH (not terminal)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    token = await _setup_webhook_tenant()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_nomatch_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": "pay_nonexistent"},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_found"] is False
    assert resp.json()["state"] == "PENDING_MATCH"


@pytest.mark.asyncio
async def test_webhook_pending_match_allows_retry(client, monkeypatch):
    """A PENDING_MATCH event can be retried and processed when payment appears."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    token = await _setup_webhook_tenant()
    event_id = f"evt_retry_{uuid.uuid4().hex[:8]}"

    # First attempt: payment doesn't exist
    resp1 = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": event_id,
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": "pay_retry_test"},
        },
        headers={"asaas-access-token": token},
    )
    assert resp1.status_code == 200
    assert resp1.json()["state"] == "PENDING_MATCH"

    # Now create the payment
    payment_id, _provider_pid = await _create_payment()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        p = (await db.execute(select(Payment).where(Payment.id == payment_id))).scalar_one()
        p.provider_payment_id = "pay_retry_test"
        await db.commit()

    # Second attempt: same event, now payment exists
    resp2 = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": event_id,
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": "pay_retry_test"},
        },
        headers={"asaas-access-token": token},
    )
    assert resp2.status_code == 200
    assert resp2.json()["state"] == "PROCESSED"
    assert resp2.json()["payment_status"] == "APROVADO"


@pytest.mark.asyncio
async def test_webhook_processed_event_is_terminal(client, monkeypatch):
    """A PROCESSED event cannot be reprocessed."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    token = await _setup_webhook_tenant()
    _payment_id, provider_pid = await _create_payment()

    event_id = f"evt_term_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": event_id,
        "event": "PAYMENT_RECEIVED",
        "payment": {"id": provider_pid},
    }

    # First: process
    resp1 = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json=payload,
        headers={"asaas-access-token": token},
    )
    assert resp1.status_code == 200
    assert resp1.json()["state"] == "PROCESSED"

    # Second: duplicate should be acknowledged as terminal
    resp2 = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json=payload,
        headers={"asaas-access-token": token},
    )
    assert resp2.status_code == 200
    assert resp2.json()["duplicate"] is True


@pytest.mark.asyncio
async def test_webhook_unknown_event_ignored_terminal(client, monkeypatch):
    """Unknown events are IGNORED (terminal, safe)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    token = await _setup_webhook_tenant()
    _payment_id, provider_pid = await _create_payment()

    event_id = f"evt_unk_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": event_id,
            "event": "PAYMENT_SOME_FUTURE_EVENT",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["unknown_event"] is True
    assert resp.json()["state"] == "IGNORED"

    # Retry should be duplicate (terminal)
    resp2 = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": event_id,
            "event": "PAYMENT_SOME_FUTURE_EVENT",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": token},
    )
    assert resp2.json()["duplicate"] is True


# ─── Event mapping tests ───

@pytest.mark.asyncio
async def test_webhook_payment_confirmed_maps_to_aprovado(client, monkeypatch):
    """PAYMENT_CONFIRMED maps to APROVADO."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    token = await _setup_webhook_tenant()
    _payment_id, provider_pid = await _create_payment()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_conf_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_CONFIRMED",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "APROVADO"


@pytest.mark.asyncio
async def test_webhook_payment_refunded_maps_to_reembolsado(client, monkeypatch):
    """PAYMENT_REFUNDED maps to REEMBOLSADO."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    token = await _setup_webhook_tenant()
    _payment_id, provider_pid = await _create_payment()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_ref_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_REFUNDED",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "REEMBOLSADO"


@pytest.mark.asyncio
async def test_webhook_chargeback_maps_to_recusado(client, monkeypatch):
    """PAYMENT_CHARGEBACK_REQUESTED maps to RECUSADO."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    token = await _setup_webhook_tenant()
    _payment_id, provider_pid = await _create_payment()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_cb_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_CHARGEBACK_REQUESTED",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "RECUSADO"


@pytest.mark.asyncio
async def test_webhook_payment_overdue_maps_to_processando(client, monkeypatch):
    """PAYMENT_OVERDUE maps to PROCESSANDO (may still be paid)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    token = await _setup_webhook_tenant()
    _payment_id, provider_pid = await _create_payment()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_od_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_OVERDUE",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "PROCESSANDO"


@pytest.mark.asyncio
async def test_webhook_credit_card_capture_refused_maps_to_recusado(client, monkeypatch):
    """PAYMENT_CREDIT_CARD_CAPTURE_REFUSED maps to RECUSADO."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    token = await _setup_webhook_tenant()
    _payment_id, provider_pid = await _create_payment()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_cc_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["payment_status"] == "RECUSADO"
