import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.models.tenant import Tenant
from app.schemas.tenant import CustomDomainIn, CustomDomainOut

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
async def list_plans():
    """Retorna os planos disponíveis para comercialização."""
    return [
        {
            "name": "Starter",
            "price": 97.0,
            "description": "Ideal para pequenas consultorias iniciando com treinamentos digitais.",
            "features": ["1 domínio customizado", "Até 50 alunos", "Suporte por e-mail"],
        },
        {
            "name": "Pro",
            "price": 297.0,
            "description": "Para empresas que precisam escalar a capacitação.",
            "features": ["5 domínios customizados", "Até 500 alunos", "Suporte prioritário", "Relatórios avançados"],
        },
        {
            "name": "Enterprise",
            "price": 997.0,
            "description": "Solução completa com integrações e volume ilimitado.",
            "features": ["Domínios ilimitados", "Alunos ilimitados", "Suporte 24/7", "API dedicada", "White label completo"],
        },
    ]


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


@router.post("/custom-domain", response_model=CustomDomainOut)
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

    tenant.custom_domain = domain
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
    await db.commit()
    await db.refresh(tenant)
    return tenant
