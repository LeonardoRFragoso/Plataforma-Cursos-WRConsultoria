"""Tests for payment customer synchronization service."""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.company import Company
from app.models.payment import PaymentCustomer, PaymentProvider
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.asaas_provider import AsaasProvider
from app.services.payment_customer_sync import (
    get_or_create_company_customer,
    get_or_create_student_customer,
)


async def _create_student_with_user(email, full_name, tenant_id, cpf=None):
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=email,
            full_name=full_name,
            cpf=cpf or str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.flush()
        student = Student(
            user_id=user.id,
            tenant_id=tenant_id,
            cpf=cpf or str(uuid.uuid4().int)[:11],
            phone="11999999999",
        )
        db.add(student)
        await db.commit()
        await db.refresh(student)
        await db.refresh(user)
        return student.id, user.id


async def _create_company(tenant_id, legal_name, cnpj):
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        company = Company(
            tenant_id=tenant_id,
            legal_name=legal_name,
            cnpj=cnpj,
            rh_name="RH Contact",
            rh_email="rh@company.test",
            rh_phone="11888888888",
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)
        return company.id


@pytest.mark.asyncio
async def test_student_customer_create_and_reuse():
    """Creating a student customer twice reuses the mapping."""
    student_id, _ = await _create_student_with_user(
        "sync_stu@wr.test", "Sync Student", WR_TENANT_ID, cpf="12345678901"
    )
    provider = AsaasProvider(api_key="test-key", mock=True)

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        cid1 = await get_or_create_student_customer(
            db,
            provider,
            tenant_id=WR_TENANT_ID,
            student_id=student_id,
            provider_name=PaymentProvider.ASAAS,
        )
        await db.commit()

    assert cid1.startswith("mock-cus-stu-")

    # Second call should reuse, not create a new mapping
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        cid2 = await get_or_create_student_customer(
            db,
            provider,
            tenant_id=WR_TENANT_ID,
            student_id=student_id,
            provider_name=PaymentProvider.ASAAS,
        )
        await db.commit()

    assert cid2 == cid1

    # Verify only one mapping in DB
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        stmt = select(PaymentCustomer).where(
            PaymentCustomer.student_id == student_id,
            PaymentCustomer.provider == PaymentProvider.ASAAS,
        )
        mappings = (await db.execute(stmt)).scalars().all()
        assert len(mappings) == 1


@pytest.mark.asyncio
async def test_company_customer_create_and_reuse():
    """Creating a company customer twice reuses the mapping."""
    company_id = await _create_company(WR_TENANT_ID, "Test Company Ltd", "12345678000190")
    provider = AsaasProvider(api_key="test-key", mock=True)

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        cid1 = await get_or_create_company_customer(
            db,
            provider,
            tenant_id=WR_TENANT_ID,
            company_id=company_id,
            provider_name=PaymentProvider.ASAAS,
        )
        await db.commit()

    assert cid1.startswith("mock-cus-com-")

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        cid2 = await get_or_create_company_customer(
            db,
            provider,
            tenant_id=WR_TENANT_ID,
            company_id=company_id,
            provider_name=PaymentProvider.ASAAS,
        )
        await db.commit()

    assert cid2 == cid1


@pytest.mark.asyncio
async def test_student_customer_cross_tenant_isolation():
    """Student customer lookup is tenant-scoped — different tenants get different mappings."""
    from app.models.tenant import Tenant, TenantStatus

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

    # Create student in WR
    wr_student_id, _ = await _create_student_with_user(
        "wr_sync@wr.test", "WR Sync", WR_TENANT_ID, cpf="11122233344"
    )

    provider = AsaasProvider(api_key="test-key", mock=True)

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        await get_or_create_student_customer(
            db,
            provider,
            tenant_id=WR_TENANT_ID,
            student_id=wr_student_id,
            provider_name=PaymentProvider.ASAAS,
        )
        await db.commit()

    # Looking up the same student_id from Alfa tenant should fail (student not in Alfa)
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        with pytest.raises(ValueError, match="not found in tenant"):
            await get_or_create_student_customer(
                db,
                provider,
                tenant_id=alfa_id,
                student_id=wr_student_id,
                provider_name=PaymentProvider.ASAAS,
            )
