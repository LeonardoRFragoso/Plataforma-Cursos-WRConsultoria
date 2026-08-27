import pytest


VALID_CNPJ = "11222333000181"


@pytest.mark.asyncio
async def test_public_corporate_request_rejects_invalid_cnpj(client):
    response = await client.post(
        "/api/v1/corporate/requests",
        json={
            "company_name": "Empresa Inválida",
            "cnpj": "11222333000180",
            "contact_name": "Responsável",
            "contact_email": "responsavel@example.com",
            "employee_count": 10,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_converts_lead_to_company_idempotently(client, admin_headers):
    lead_response = await client.post(
        "/api/v1/corporate/requests",
        json={
            "company_name": "Empresa Contratante Ltda",
            "cnpj": VALID_CNPJ,
            "contact_name": "Responsável RH",
            "contact_email": "rh.contratante@example.com",
            "contact_phone": "21999999999",
            "employee_count": 25,
            "course_interest": "NR-10",
        },
    )
    assert lead_response.status_code == 201
    request_id = lead_response.json()["id"]

    first = await client.post(
        f"/api/v1/corporate/requests/{request_id}/convert",
        json={"contract_reference": "PROP-2026-001"},
        headers=admin_headers,
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["created"] is True
    assert first_payload["status"] == "WON"

    second = await client.post(
        f"/api/v1/corporate/requests/{request_id}/convert",
        json={},
        headers=admin_headers,
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["created"] is False
    assert second_payload["company_id"] == first_payload["company_id"]

    companies = await client.get("/api/v1/companies/", headers=admin_headers)
    assert companies.status_code == 200
    matching = [company for company in companies.json() if company["cnpj"] == VALID_CNPJ]
    assert len(matching) == 1
    assert matching[0]["legal_name"] == "Empresa Contratante Ltda"
