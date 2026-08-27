import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.normalization import is_valid_cnpj
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.course import Course
from app.models.tenant import CustomDomainStatus, Tenant
from app.schemas.tenant import (
    CustomDomainIn,
    CustomDomainOut,
    CustomDomainVerifyOut,
    TenantBrandingResponse,
    TenantBrandingUpdate,
)
from app.services.domain_verification import (
    build_dns_instructions,
    get_domain_verification_provider,
)
from app.services.tenant_secret_service import (
    get_asaas_api_key,
    get_mercado_pago_access_token,
    get_tenant_secret,
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


class ReadinessItem(BaseModel):
    key: str
    label: str
    ready: bool
    required: bool = True
    detail: str


class TenantReadinessOut(BaseModel):
    ready_for_launch: bool
    completed: int
    total_required: int
    percentage: int
    payment_provider: str | None = None
    active_courses: int
    items: list[ReadinessItem]


@router.get("/branding", response_model=TenantBrandingOut)
async def get_branding_by_domain(
    slug: str = Query(default="wr"),
    db: AsyncSession = Depends(get_db),
):
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


@router.put("/branding", response_model=TenantBrandingResponse)
async def update_tenant_branding(
    data: TenantBrandingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Atualiza branding do tenant atual (admin ou super_admin)."""
    tenant_id = get_current_tenant_id()
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(tenant, field, value)

    await db.commit()
    await db.refresh(tenant)
    return TenantBrandingResponse.model_validate(tenant)


@router.get("/readiness", response_model=TenantReadinessOut)
async def get_tenant_readiness(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Compute the tenant launch checklist from real persisted configuration.

    Nothing in this response is manually checked. A tenant only reaches 100%
    when the required identity, branding, routing, payment and catalog data are
    actually present and usable by the platform.
    """
    tenant_id = get_current_tenant_id()
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    active_courses = int(
        await db.scalar(
            select(func.count(Course.id)).where(
                Course.tenant_id == tenant_id,
                Course.is_active.is_(True),
            )
        )
        or 0
    )

    tenant_settings = tenant.settings or {}
    payment_provider = str(tenant_settings.get("payment_provider") or "").upper() or None
    gateway_ready = False
    gateway_detail = "Selecione e configure um gateway de pagamento."
    if payment_provider == "ASAAS":
        api_key = await get_asaas_api_key(db, tenant_id)
        webhook_token = await get_tenant_secret(db, tenant_id, "asaas_webhook_token")
        connection_valid = bool(tenant_settings.get("asaas_last_validation_at"))
        webhook_ready = bool(tenant_settings.get("asaas_webhook_id")) and bool(
            tenant_settings.get("asaas_webhook_enabled")
        ) and bool(webhook_token) and not bool(tenant_settings.get("asaas_webhook_interrupted", True))
        gateway_ready = bool(api_key) and connection_valid and webhook_ready
        gateway_detail = (
            "Asaas validado e webhook operacional."
            if gateway_ready
            else "Asaas precisa de credencial válida, validação de conexão e webhook operacional."
        )
    elif payment_provider in {"MERCADO_PAGO", "MERCADOPAGO"}:
        gateway_ready = bool(await get_mercado_pago_access_token(db, tenant_id))
        gateway_detail = (
            "Mercado Pago possui credencial de tenant configurada."
            if gateway_ready
            else "Configure a credencial do Mercado Pago para este tenant."
        )

    identity_ready = bool(
        tenant.name
        and tenant.legal_name
        and tenant.cnpj
        and is_valid_cnpj(tenant.cnpj)
        and tenant.contact_name
        and tenant.contact_email
    )
    branding_ready = bool(tenant.logo_url and tenant.primary_color and tenant.secondary_color)
    domain_ready = bool(tenant.slug) and (
        not tenant.custom_domain
        or tenant.custom_domain_status in {CustomDomainStatus.VERIFIED, CustomDomainStatus.ACTIVE, "VERIFIED", "ACTIVE"}
    )
    catalog_ready = active_courses > 0
    certificate_ready = active_courses > 0

    items = [
        ReadinessItem(
            key="identity",
            label="Identidade da empresa",
            ready=identity_ready,
            detail=(
                "Razão social, CNPJ válido e contato principal preenchidos."
                if identity_ready
                else "Preencha razão social, CNPJ válido e contato principal do tenant."
            ),
        ),
        ReadinessItem(
            key="branding",
            label="Branding",
            ready=branding_ready,
            detail=(
                "Logo e paleta principal configurados."
                if branding_ready
                else "Configure logo, cor primária e cor secundária."
            ),
        ),
        ReadinessItem(
            key="domain",
            label="Domínio",
            ready=domain_ready,
            detail=(
                "Roteamento disponível pelo slug ou domínio customizado verificado."
                if domain_ready
                else "O domínio customizado informado ainda precisa ser verificado."
            ),
        ),
        ReadinessItem(
            key="gateway",
            label="Gateway de pagamento",
            ready=gateway_ready,
            detail=gateway_detail,
        ),
        ReadinessItem(
            key="catalog",
            label="Catálogo",
            ready=catalog_ready,
            detail=(
                f"{active_courses} curso(s) ativo(s) disponível(is)."
                if catalog_ready
                else "Publique ao menos um curso ativo."
            ),
        ),
        ReadinessItem(
            key="certificates",
            label="Certificação",
            ready=certificate_ready,
            detail=(
                "Emissão e validação pública de certificados disponíveis para o catálogo ativo."
                if certificate_ready
                else "A certificação fica disponível após existir catálogo ativo."
            ),
        ),
    ]

    required_items = [item for item in items if item.required]
    completed = sum(1 for item in required_items if item.ready)
    total_required = len(required_items)
    percentage = round((completed / total_required) * 100) if total_required else 100
    return TenantReadinessOut(
        ready_for_launch=completed == total_required,
        completed=completed,
        total_required=total_required,
        percentage=percentage,
        payment_provider=payment_provider,
        active_courses=active_courses,
        items=items,
    )


@router.get("/plans")
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Retorna os planos comerciais públicos do catálogo da WR (DB)."""
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
    except (HTTPException, ValueError, RuntimeError) as exc:
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
