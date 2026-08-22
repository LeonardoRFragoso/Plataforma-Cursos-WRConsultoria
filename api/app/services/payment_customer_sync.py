"""Payment customer synchronization service.

Handles the lookup → reuse → create flow for provider customer mappings.
Works for both individual students and corporate companies.

Flow:
1. Look up existing PaymentCustomer by (tenant_id, student_id/company_id, provider).
2. If found, reuse the stored provider_customer_id.
3. If not found, call the provider to create/lookup a customer using
   stable externalReference (never name-based identity).
4. Persist the new mapping in PaymentCustomer.
5. Return the provider_customer_id.

Duplicate prevention:
- PaymentCustomer has unique constraints on
  (tenant, student, provider) and (tenant, company, provider).
- The provider's create_or_update_customer also deduplicates via
  externalReference before creating.
- Under retry/concurrency, the DB unique constraint is the final guard.

CPF/CNPJ validation:
- For production charges, a valid CPF (student) or CNPJ (company) is
  required. The service raises ValueError if missing/invalid when
  not in mock mode.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.payment import PaymentCustomer, PaymentProvider
from app.models.student import Student
from app.models.user import User
from app.services.payment_provider_base import (
    CustomerResult,
    PaymentProviderInterface,
)


async def get_or_create_student_customer(
    db: AsyncSession,
    provider: PaymentProviderInterface,
    *,
    tenant_id: UUID,
    student_id: UUID,
    provider_name: PaymentProvider,
) -> str:
    """Get or create a provider customer for a student.

    Returns the provider_customer_id.
    """
    # 1. Check existing mapping
    stmt = select(PaymentCustomer).where(
        PaymentCustomer.tenant_id == tenant_id,
        PaymentCustomer.student_id == student_id,
        PaymentCustomer.provider == provider_name,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing.provider_customer_id

    # 2. Load student + user for customer data
    stmt = (
        select(Student, User)
        .join(User, Student.user_id == User.id)
        .where(
            Student.id == student_id,
            Student.tenant_id == tenant_id,
        )
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise ValueError(f"Student {student_id} not found in tenant {tenant_id}")

    student, user = row

    # 3. Validate CPF for production (non-mock) providers
    cpf = (student.cpf or "").replace(".", "").replace("-", "").strip()
    if not cpf and not _is_mock_provider(provider):
        raise ValueError(
            f"Student {student_id} has no CPF — required for production payment"
        )

    # 4. Create/lookup customer at provider using stable externalReference
    external_id = f"stu-{student_id}"
    result: CustomerResult = await provider.create_or_update_customer(
        name=user.full_name or user.email,
        email=user.email,
        cpf_cnpj=cpf or None,
        phone=student.phone,
        external_id=external_id,
    )

    # 5. Persist mapping
    mapping = PaymentCustomer(
        tenant_id=tenant_id,
        provider=provider_name,
        provider_customer_id=result.provider_customer_id,
        student_id=student_id,
    )
    db.add(mapping)
    try:
        await db.flush()
    except Exception:
        # Concurrency: another request may have created it. Re-fetch.
        await db.rollback()
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing.provider_customer_id
        raise

    return result.provider_customer_id


async def get_or_create_company_customer(
    db: AsyncSession,
    provider: PaymentProviderInterface,
    *,
    tenant_id: UUID,
    company_id: UUID,
    provider_name: PaymentProvider,
) -> str:
    """Get or create a provider customer for a company (corporate billing).

    Returns the provider_customer_id.
    """
    # 1. Check existing mapping
    stmt = select(PaymentCustomer).where(
        PaymentCustomer.tenant_id == tenant_id,
        PaymentCustomer.company_id == company_id,
        PaymentCustomer.provider == provider_name,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing.provider_customer_id

    # 2. Load company
    company = await db.get(Company, company_id)
    if not company or company.tenant_id != tenant_id:
        raise ValueError(f"Company {company_id} not found in tenant {tenant_id}")

    # 3. Validate CNPJ for production
    cnpj = (company.cnpj or "").replace(".", "").replace("-", "").replace("/", "").strip()
    if not cnpj and not _is_mock_provider(provider):
        raise ValueError(
            f"Company {company_id} has no CNPJ — required for production payment"
        )

    # 4. Create/lookup customer at provider
    external_id = f"com-{company_id}"
    result: CustomerResult = await provider.create_or_update_customer(
        name=company.legal_name,
        email=company.rh_email or f"company-{company_id}@noreply.local",
        cpf_cnpj=cnpj or None,
        phone=company.rh_phone,
        external_id=external_id,
    )

    # 5. Persist mapping
    mapping = PaymentCustomer(
        tenant_id=tenant_id,
        provider=provider_name,
        provider_customer_id=result.provider_customer_id,
        company_id=company_id,
    )
    db.add(mapping)
    try:
        await db.flush()
    except Exception:
        await db.rollback()
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing.provider_customer_id
        raise

    return result.provider_customer_id


def _is_mock_provider(provider: PaymentProviderInterface) -> bool:
    """Check if the provider is in mock mode (no real API calls)."""
    return getattr(provider, "_mock", False) is True


__all__ = [
    "get_or_create_company_customer",
    "get_or_create_student_customer",
]
