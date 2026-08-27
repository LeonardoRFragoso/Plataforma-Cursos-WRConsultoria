import uuid

import pytest

from tests.cnpj_utils import make_valid_cnpj


@pytest.mark.asyncio
async def test_company_persists_corporate_billing_and_contract_metadata(client, admin_headers):
    payload = {
        "legal_name": f"Empresa B2B {uuid.uuid4().hex[:8]}",
        "trade_name": "Empresa B2B",
        "cnpj": make_valid_cnpj(),
        "rh_name": "Responsável RH",
        "rh_email": f"rh-{uuid.uuid4().hex[:8]}@example.com",
        "billing_email": f"financeiro-{uuid.uuid4().hex[:8]}@example.com",
        "contract_reference": "CONTRATO-B2B-001",
        "status": "active",
        "notes": "Condição comercial homologada",
    }

    created = await client.post("/api/v1/companies/", json=payload, headers=admin_headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["billing_email"] == payload["billing_email"]
    assert body["contract_reference"] == payload["contract_reference"]
    assert body["status"] == "ACTIVE"
    assert body["notes"] == payload["notes"]

    fetched = await client.get(f"/api/v1/companies/{body['id']}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["billing_email"] == payload["billing_email"]
    assert fetched.json()["contract_reference"] == payload["contract_reference"]


@pytest.mark.asyncio
async def test_company_update_normalizes_corporate_status_and_billing_email(client, admin_headers):
    created = await client.post(
        "/api/v1/companies/",
        json={
            "legal_name": f"Empresa Update {uuid.uuid4().hex[:8]}",
            "cnpj": make_valid_cnpj(),
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text

    billing_email = f"cobranca-{uuid.uuid4().hex[:8]}@example.com"
    updated = await client.put(
        f"/api/v1/companies/{created.json()['id']}",
        json={
            "billing_email": billing_email,
            "contract_reference": "NOVO-CONTRATO",
            "status": "suspended",
            "notes": "Contrato temporariamente suspenso",
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["billing_email"] == billing_email
    assert body["contract_reference"] == "NOVO-CONTRATO"
    assert body["status"] == "SUSPENDED"
    assert body["notes"] == "Contrato temporariamente suspenso"
