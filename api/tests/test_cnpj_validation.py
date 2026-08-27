import pytest
from pydantic import ValidationError

from app.core.normalization import (
    is_cnpj_format,
    is_valid_cnpj,
    normalize_cnpj,
    validate_cnpj,
)
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.schemas.corporate import CorporateRequestCreate


def test_validate_cnpj_accepts_raw_and_formatted():
    assert validate_cnpj("04.252.011/0001-10") == "04252011000110"
    assert validate_cnpj("04252011000110") == "04252011000110"


@pytest.mark.parametrize(
    "value",
    [
        "04.252.011/0001-11",
        "11.111.111/1111-11",
        "12345678000199",
        "abc04252011000110xyz",
    ],
)
def test_validate_cnpj_rejects_invalid(value):
    assert not is_valid_cnpj(value)
    with pytest.raises(ValueError, match="CNPJ"):
        validate_cnpj(value)


def test_cnpj_format_contract():
    assert is_cnpj_format("04.252.011/0001-10")
    assert is_cnpj_format("04252011000110")
    assert not is_cnpj_format("04.252.0110001-10")
    assert normalize_cnpj("04.252.011/0001-10") == "04252011000110"


def test_company_schemas_normalize_cnpj():
    created = CompanyCreate(legal_name="Empresa Teste", cnpj="04.252.011/0001-10")
    assert created.cnpj == "04252011000110"

    updated = CompanyUpdate(cnpj="11.222.333/0001-81")
    assert updated.cnpj == "11222333000181"


def test_corporate_request_schema_normalizes_cnpj():
    lead = CorporateRequestCreate(
        company_name="Empresa Teste",
        cnpj="04.252.011/0001-10",
        contact_name="Responsável",
        contact_email="rh@example.com",
    )
    assert lead.cnpj == "04252011000110"


def test_company_schema_rejects_bad_check_digits():
    with pytest.raises(ValidationError):
        CompanyCreate(legal_name="Empresa Teste", cnpj="04.252.011/0001-11")


def test_corporate_request_schema_rejects_bad_check_digits():
    with pytest.raises(ValidationError):
        CorporateRequestCreate(
            company_name="Empresa Teste",
            cnpj="04.252.011/0001-11",
            contact_name="Responsável",
            contact_email="rh@example.com",
        )


@pytest.mark.asyncio
async def test_company_update_duplicate_cnpj_returns_conflict(client, admin_headers):
    first = await client.post(
        "/api/v1/companies/",
        json={"legal_name": "Empresa CNPJ A", "cnpj": "04.252.011/0001-10"},
        headers=admin_headers,
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/v1/companies/",
        json={"legal_name": "Empresa CNPJ B", "cnpj": "11.222.333/0001-81"},
        headers=admin_headers,
    )
    assert second.status_code == 201, second.text

    duplicated = await client.put(
        f"/api/v1/companies/{second.json()['id']}",
        json={"cnpj": "04.252.011/0001-10"},
        headers=admin_headers,
    )
    assert duplicated.status_code == 409, duplicated.text
    assert "CNPJ" in duplicated.json()["detail"]
