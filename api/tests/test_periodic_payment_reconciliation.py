import pytest

from app.models.payment import PaymentProvider, PaymentStatus
from app.services.periodic_payment_reconciliation import provider_status_action


def test_asaas_periodic_status_mapping():
    assert provider_status_action(PaymentProvider.ASAAS, "PENDING").value == PaymentStatus.PROCESSANDO
    assert provider_status_action(PaymentProvider.ASAAS, "OVERDUE").value == PaymentStatus.PROCESSANDO
    assert provider_status_action(PaymentProvider.ASAAS, "RECEIVED").value == PaymentStatus.APROVADO
    refunded = provider_status_action(PaymentProvider.ASAAS, "REFUNDED")
    assert refunded.kind == "special"
    assert refunded.value == "PAYMENT_REFUNDED"
    chargeback = provider_status_action(PaymentProvider.ASAAS, "CHARGEBACK_DISPUTE")
    assert chargeback.value == "PAYMENT_CHARGEBACK_DISPUTE"


def test_mercado_pago_periodic_status_mapping():
    assert provider_status_action(PaymentProvider.MERCADO_PAGO, "approved").value == PaymentStatus.APROVADO
    assert provider_status_action(PaymentProvider.MERCADO_PAGO, "rejected").value == PaymentStatus.RECUSADO
    assert provider_status_action(PaymentProvider.MERCADO_PAGO, "cancelled").value == "MERCADO_PAGO_CANCELLED"
    assert provider_status_action(PaymentProvider.MERCADO_PAGO, "refunded").value == "MERCADO_PAGO_REFUNDED"
    assert (
        provider_status_action(PaymentProvider.MERCADO_PAGO, "charged_back", "settled").value
        == "MERCADO_PAGO_CHARGEBACK_SETTLED"
    )
    assert (
        provider_status_action(PaymentProvider.MERCADO_PAGO, "charged_back", "reimbursed").value
        == "MERCADO_PAGO_CHARGEBACK_REIMBURSED"
    )


def test_unknown_provider_status_is_non_destructive():
    action = provider_status_action(PaymentProvider.ASAAS, "FUTURE_STATUS_NOT_KNOWN")
    assert action.kind == "ignore"
    assert action.value == "FUTURE_STATUS_NOT_KNOWN"


@pytest.mark.asyncio
async def test_admin_can_trigger_reconciliation_without_money_movement(client, admin_headers, monkeypatch):
    async def fake_reconcile(db, tenant_id, *, limit=250):
        assert db is not None
        assert tenant_id is not None
        assert limit == 25
        return {
            "scanned": 3,
            "reconciled": 3,
            "changed": 1,
            "reviews_opened": 1,
            "ignored": 1,
            "failed": 0,
        }

    monkeypatch.setattr(
        "app.api.routes.reconciliation.reconcile_tenant_payments",
        fake_reconcile,
    )
    response = await client.post(
        "/api/v1/financial/reconciliation/run?limit=25",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["scanned"] == 3
    assert response.json()["reviews_opened"] == 1


@pytest.mark.asyncio
async def test_student_cannot_trigger_financial_reconciliation(client, student_user):
    response = await client.post(
        "/api/v1/financial/reconciliation/run",
        headers=student_user["headers"],
    )
    assert response.status_code == 403
