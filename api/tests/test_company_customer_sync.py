"""Tests for payment_customer_sync company customer creation."""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.company import Company
from app.models.payment import PaymentCustomer, PaymentProvider
from app.services.payment_customer_sync import get_or_create_company_customer
from app.services.payment_provider_base import CustomerResult


async def _create_company(cnpj="12345678000190"):
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        company = Company(
            tenant_id=WR_TENANT_ID,
            legal_name=f"Test Company {uuid.uuid4().hex[:6]}",
            cnpj=cnpj,
            rh_email="rh@test.com",
            rh_phone="11999999999",
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)
        return company.id


class MockProvider:
    """Mock provider for testing customer sync."""
    provider = PaymentProvider.ASAAS
    _mock = True

    async def create_or_update_customer(self, **kwargs):
        return CustomerResult(provider_customer_id="cus_mock_123", raw={})


class MockProviderNonMock:
    """Mock provider that's not in mock mode."""
    provider = PaymentProvider.ASAAS
    _mock = False

    async def create_or_update_customer(self, **kwargs):
        return CustomerResult(provider_customer_id="cus_real_123", raw={})


@pytest.mark.asyncio
async def test_get_or_create_company_customer_new():
    """Create a new company customer mapping."""
    company_id = await _create_company()

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        provider = MockProvider()
        result = await get_or_create_company_customer(
            db,
            provider,
            tenant_id=WR_TENANT_ID,
            company_id=company_id,
            provider_name=PaymentProvider.ASAAS,
        )
        await db.commit()  # commit so the mapping persists

    assert result == "cus_mock_123"

    # Verify mapping was persisted
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        mapping = (await db.execute(
            select(PaymentCustomer).where(
                PaymentCustomer.tenant_id == WR_TENANT_ID,
                PaymentCustomer.company_id == company_id,
                PaymentCustomer.provider == PaymentProvider.ASAAS,
            )
        )).scalar_one_or_none()
        assert mapping is not None
        assert mapping.provider_customer_id == "cus_mock_123"


@pytest.mark.asyncio
async def test_get_or_create_company_customer_reuse():
    """Reuse existing company customer mapping."""
    company_id = await _create_company(cnpj="98765432000110")

    # Create existing mapping
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        mapping = PaymentCustomer(
            tenant_id=WR_TENANT_ID,
            provider=PaymentProvider.ASAAS,
            provider_customer_id="cus_existing_456",
            company_id=company_id,
        )
        db.add(mapping)
        await db.commit()

    # Second call should reuse
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        provider = MockProvider()
        result = await get_or_create_company_customer(
            db,
            provider,
            tenant_id=WR_TENANT_ID,
            company_id=company_id,
            provider_name=PaymentProvider.ASAAS,
        )

    assert result == "cus_existing_456"


@pytest.mark.asyncio
async def test_get_or_create_company_customer_no_cnpj_non_mock():
    """Company without CNPJ in non-mock mode raises ValueError."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        company = Company(
            tenant_id=WR_TENANT_ID,
            legal_name="No CNPJ Company",
            cnpj="",  # Empty string (not null)
            rh_email="rh@nocnpj.com",
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)
        company_id = company.id

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        provider = MockProviderNonMock()
        with pytest.raises(ValueError, match="CNPJ"):
            await get_or_create_company_customer(
                db,
                provider,
                tenant_id=WR_TENANT_ID,
                company_id=company_id,
                provider_name=PaymentProvider.ASAAS,
            )


@pytest.mark.asyncio
async def test_get_or_create_company_customer_not_found():
    """Non-existent company raises ValueError."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        provider = MockProvider()
        with pytest.raises(ValueError, match="not found"):
            await get_or_create_company_customer(
                db,
                provider,
                tenant_id=WR_TENANT_ID,
                company_id=uuid.uuid4(),
                provider_name=PaymentProvider.ASAAS,
            )
