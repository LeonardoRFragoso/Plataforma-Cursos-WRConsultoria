import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.tenant import CustomDomainStatus, Tenant
from app.schemas.tenant import CustomDomainIn, CustomDomainOut, CustomDomainVerifyOut
from app.services.domain_verification import (
    build_dns_instructions,
    get_domain_verification_provider,
)

router = APIRouter()


class TenantBrandingOut(BaseModel):
    name: str
    logo_url: str | None
    logo_white_url: str | None
    favicon_url: str | None
    primary_color: str | None
    secondary_color: str | None
    accent_color: str | None


@router.get("/branding", response_model=TenantBrandingOut)
async def get_branding_by_domain(
    slug: str = Query(default="wr"),
    db: AsyncSession = Depends(get_db),
):
    from app.models.tenant import Tenant

    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return TenantBrandingOut(
        name=tenant.name,
        logo_url=tenant.logo_url,
        logo_white_url=tenant.logo_white_url,
        favicon_url=tenant.favicon_url,
        primary_color=tenant.primary_color,
        secondary_color=tenant.secondary_color,
        accent_color=tenant.accent_color,
    )


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Retorna os planos comerciais públicos do catálogo da WR (DB).

    Fonte única de verdade: tabela Plan (catálogo global, tenant_id NULL).
    Equivalente a GET /api/v1/plans/public — mantido aqui por
    compatibilidade de rota pública no storefront de tenants.
    """
    from app.models.plan import Plan

    stmt = select(Plan).where(
        Plan.tenant_id.is_(None),
        Plan.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalars().all()


def _normalize_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    return domain.strip().lower()


@router.get("/custom-domain", response_model=CustomDomainOut)
async def get_custom_domain(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


@router.post("/custom-domain", response_model=CustomDomainVerifyOut)
async def set_custom_domain(
    data: CustomDomainIn,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    domain = _normalize_domain(data.custom_domain)
    if not domain or not re.match(r"^[a-z0-9][a-z0-9\-\.]+[a-z0-9]+$", domain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid custom domain",
        )

    existing = (
        await db.execute(
            select(Tenant).where(
                Tenant.custom_domain == domain,
                Tenant.id != tenant_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Custom domain already in use",
        )

    # Registra domínio em PENDING com token seguro; nunca ACTIVE apenas por
    # ter sido digitado.
    tenant.custom_domain = domain
    tenant.custom_domain_status = CustomDomainStatus.PENDING
    tenant.domain_verification_token = secrets.token_urlsafe(32)
    tenant.domain_verified_at = None
    tenant.domain_verification_error = None
    await db.commit()
    await db.refresh(tenant)

    out = CustomDomainVerifyOut.model_validate(tenant)
    out.dns_instructions = build_dns_instructions(
        domain, tenant.domain_verification_token
    )
    return out


@router.post("/custom-domain/verify", response_model=CustomDomainOut)
async def verify_custom_domain(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    if not tenant.custom_domain or not tenant.domain_verification_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No custom domain registered",
        )

    provider = get_domain_verification_provider()
    try:
        ok = await provider.verify_txt(
            tenant.custom_domain, tenant.domain_verification_token
        )
    except (HTTPException, ValueError, RuntimeError) as exc:  # provider robustez
        tenant.custom_domain_status = CustomDomainStatus.ERROR
        tenant.domain_verification_error = str(exc)
        await db.commit()
        await db.refresh(tenant)
        return tenant

    if ok:
        tenant.custom_domain_status = CustomDomainStatus.VERIFIED
        tenant.domain_verified_at = utc_now()
        tenant.domain_verification_error = None
    else:
        tenant.custom_domain_status = CustomDomainStatus.ERROR
        tenant.domain_verification_error = (
            "DNS TXT record not found or token mismatch"
        )
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.delete("/custom-domain", response_model=CustomDomainOut)
async def remove_custom_domain(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    tenant.custom_domain = None
    tenant.custom_domain_status = CustomDomainStatus.NONE
    tenant.domain_verification_token = None
    tenant.domain_verified_at = None
    tenant.domain_verification_error = None
    await db.commit()
    await db.refresh(tenant)
    return tenant
