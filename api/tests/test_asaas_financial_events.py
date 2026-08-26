import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.payment import Payment, PaymentMethod, PaymentProvider, PaymentStatus
from app.services.tenant_secret_service import set_tenant_secret


async def _setup_webhook_payment(*, status: PaymentStatus):
    token = f"financial-webhook-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        await set_tenant_secret(
            db,
            WR_TENANT_ID,
            "asaas_webhook_token",
            token,
        )
        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=None,
            company_id=None,
            amount=99.0,
            status=status,
            method=PaymentMethod.BOLETO,
            provider=PaymentProvider.ASAAS,
            provider_payment_id=f"pay_fin_{uuid.uuid4().hex[:10]}",
            checkout_url="https://asaas.example/checkout",
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        return token, payment.id, payment.provider_payment_id


@pytest.mark.asyncio
async def test_asaas_bank_slip_cancelled_marks_attempt_expired(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)
    token, payment_id, provider_payment_id = await _setup_webhook_payment(
        status=PaymentStatus.PROCESSANDO
    )

    response = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_expired_{uuid.uuid4().hex[:10]}",
            "event": "PAYMENT_BANK_SLIP_CANCELLED",
            "payment": {"id": provider_payment_id},
        },
        headers={"asaas-access-token": token},
    )

    assert response.status_code == 200
    assert response.json()["payment_status"] == "EXPIRADO"
    assert response.json()["review_required"] is False

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        assert payment.status == PaymentStatus.EXPIRADO
        assert payment.review_required is False


@pytest.mark.asyncio
async def test_asaas_chargeback_request_flags_review_without_overwriting_approval(
    client,
    monkeypatch,
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)
    token, payment_id, provider_payment_id = await _setup_webhook_payment(
        status=PaymentStatus.APROVADO
    )

    response = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_chargeback_{uuid.uuid4().hex[:10]}",
            "event": "PAYMENT_CHARGEBACK_REQUESTED",
            "payment": {"id": provider_payment_id},
        },
        headers={"asaas-access-token": token},
    )

    assert response.status_code == 200
    assert response.json()["payment_status"] == "APROVADO"
    assert response.json()["review_required"] is True

    async with AsyncSessionLocal() as db:
        payment = await db.get(Payment, payment_id)
        assert payment.status == PaymentStatus.APROVADO
        assert payment.review_required is True
        assert payment.review_reason.startswith("chargeback_review:")
