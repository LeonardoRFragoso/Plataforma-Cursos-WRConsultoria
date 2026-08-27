import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.normalization import is_valid_cnpj, normalize_cnpj, validate_cnpj
from app.models.company import Company
from app.models.payment import PaymentProvider
from app.schemas.company import CompanyCreate
from app.schemas.corporate import CorporateRequestCreate
from app.services.payment_customer_sync import get_or_create_company_customer
from app.services.payment_provider_base import CustomerResult


VALID_CNPJ = "11.222.333/0001-81"
VALID_CNPJ_DIGITS = "11222333000181"


class NonMockProviderSpy:
    provider = PaymentProvider.ASAAS
    _mock = False

    def __init__(self):
        self.calls = 0

    async def create_or_update_customer(self, **kwargs):
        self.calls += 1
        return CustomerResult(provider_customer_id="cus_real", raw={})


def test_validate_cnpj_accepts_raw_and_formatted():
    assert validate_cnpj(VALID_CNPJ) == VALID_CNPJ_DIGITS
    assert validate_cnpj(VALID_CNPJ_DIGITS) == VALID_CNPJ_DIGITS
    assert normalize_cnpj(VALID_CNPJ) == VALID_CNPJ_DIGITS
    assert is_valid_cnpj(VALID_CNPJ) is True


@pytest.mark.parametrize(
    "value",
    [
        "11.222.333/0001-80",
        "11222333000180",
        "00000000000000",
        "11111111111111",
        "abc11222333000181xyz",
        "1122233300018",
    ],
)
def test_validate_cnpj_rejects_invalid_documents(value):
    with pytest.raises(ValueError, match="CNPJ inválido"):
        validate_cnpj(value)
    assert is_valid_cnpj(value) is False


def test_company_schema_normalizes_cnpj():
    company = CompanyCreate(legal_name="Empresa Teste", cnpj=VALID_CNPJ)
    assert company.cnpj == VALID_CNPJ_DIGITS


def test_corporate_request_schema_rejects_invalid_cnpj():
    with pytest.raises(ValidationError):
        CorporateRequestCreate(
            company_name="Empresa Teste",
            cnpj="11.222.333/0001-80",
            contact_name="Contato Teste",
            contact_email="contato@example.com",
        )


@pytest.mark.asyncio
async def test_invalid_legacy_cnpj_never_reaches_real_provider():
    company_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        company = Company(
            id=company_id,
            tenant_id=WR_TENANT_ID,
            legal_name="Legacy Invalid CNPJ",
            cnpj="12345678000190",
            rh_email="financeiro@example.com",
        )
        db.add(company)
        await db.commit()

    provider = NonMockProviderSpy()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        with pytest.raises(ValueError, match="invalid CNPJ"):
            await get_or_create_company_customer(
                db,
                provider,
                tenant_id=WR_TENANT_ID,
                company_id=company_id,
                provider_name=PaymentProvider.ASAAS,
            )

    assert provider.calls == 0
