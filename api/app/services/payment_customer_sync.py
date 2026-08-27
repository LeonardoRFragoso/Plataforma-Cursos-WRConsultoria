"""Payment customer synchronization service.

Handles tenant-scoped provider customer mappings for students and companies.
Identity documents are mathematically validated before any non-mock provider
call so malformed legacy data can never create a real customer/charge path.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.normalization import validate_cnpj, validate_cpf
from app.models.company import Company
from app.models.payment import PaymentCustomer, PaymentProvider
from app.models.student import Student
from app.models.user import User
from app.services.payment_provider_base import CustomerResult, PaymentProviderInterface


async def get_or_create_student_customer(
    db: AsyncSession,
    provider: PaymentProviderInterface,
    *,
    tenant_id: UUID,
    student_id: UUID,
    provider_name: PaymentProvider,
) -> str:
    """Get or create a provider customer for a tenant-scoped student."""
    stmt = select(PaymentCustomer).where(
        PaymentCustomer.tenant_id == tenant_id,
        PaymentCustomer.student_id == student_id,
        PaymentCustomer.provider == provider_name,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing.provider_customer_id

    student_stmt = (
        select(Student, User)
        .join(User, Student.user_id == User.id)
        .where(Student.id == student_id, Student.tenant_id == tenant_id)
    )
    row = (await db.execute(student_stmt)).first()
    if not row:
        raise ValueError(f"Student {student_id} not found in tenant {tenant_id}")

    student, user = row
    cpf = (student.cpf or "").strip()
    if not _is_mock_provider(provider):
        if not cpf:
            raise ValueError(f"Student {student_id} has no CPF — required for production payment")
        try:
            cpf = validate_cpf(cpf)
        except ValueError:
            raise ValueError(
                f"Student {student_id} has invalid CPF — production payment blocked"
            ) from None
    elif cpf:
        # Keep mock paths compatible with historical fixtures while normalizing
        # valid documents whenever possible.
        try:
            cpf = validate_cpf(cpf)
        except ValueError:
            cpf = "".join(ch for ch in cpf if ch.isdigit())

    external_id = f"stu-{student_id}"
    result: CustomerResult = await provider.create_or_update_customer(
        name=user.full_name or user.email,
        email=user.email,
        cpf_cnpj=cpf or None,
        phone=student.phone,
        external_id=external_id,
    )

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
    """Get or create a provider customer for a tenant-scoped company."""
    stmt = select(PaymentCustomer).where(
        PaymentCustomer.tenant_id == tenant_id,
        PaymentCustomer.company_id == company_id,
        PaymentCustomer.provider == provider_name,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing.provider_customer_id

    company = await db.get(Company, company_id)
    if not company or company.tenant_id != tenant_id:
        raise ValueError(f"Company {company_id} not found in tenant {tenant_id}")

    cnpj = (company.cnpj or "").strip()
    if not _is_mock_provider(provider):
        if not cnpj:
            raise ValueError(f"Company {company_id} has no CNPJ — required for production payment")
        try:
            cnpj = validate_cnpj(cnpj)
        except ValueError:
            raise ValueError(
                f"Company {company_id} has invalid CNPJ — production payment blocked"
            ) from None
    elif cnpj:
        try:
            cnpj = validate_cnpj(cnpj)
        except ValueError:
            cnpj = "".join(ch for ch in cnpj if ch.isdigit())

    external_id = f"com-{company_id}"
    result: CustomerResult = await provider.create_or_update_customer(
        name=company.legal_name,
        email=company.billing_email or company.rh_email or f"company-{company_id}@noreply.local",
        cpf_cnpj=cnpj or None,
        phone=company.rh_phone,
        external_id=external_id,
    )

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


__all__ = ["get_or_create_company_customer", "get_or_create_student_customer"]
