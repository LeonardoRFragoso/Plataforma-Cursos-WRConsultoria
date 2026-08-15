"""Endpoints de SUPER_ADMIN (WR) para catálogo de Planos e lifecycle de
Assinaturas SaaS White Label.

Todas as ações usam sessão privilegada (bypass de RLS) pois operam sobre
dados globais (catálogo da WR) e sobre assinaturas de qualquer tenant.
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_privileged
from app.core.security import get_current_super_admin
from app.core.utils import utc_now
from app.models.plan import BillingCycle, Plan
from app.models.tenant import CustomDomainStatus, Tenant
from app.models.tenant_secret import TenantSecret
from app.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from app.schemas.plan import PlanCreate, PlanResponse, PlanUpdate
from app.schemas.tenant import CustomDomainOut
from app.schemas.tenant_secret import TenantSecretReveal
from app.schemas.tenant_subscription import (
    TenantSubscriptionCreate,
    TenantSubscriptionResponse,
)
from app.services.secret_crypto import decrypt

router = APIRouter()


def _end_date_for_cycle(start: datetime, billing_cycle: str):
    if billing_cycle == BillingCycle.MONTHLY:
        return start + timedelta(days=30)
    if billing_cycle == BillingCycle.YEARLY:
        return start + timedelta(days=365)
    return None


# ------------------------------------------------------------------
# Planos (catálogo comercial da WR)
# ------------------------------------------------------------------

@router.get("/plans", response_model=list[PlanResponse])
async def super_list_plans(
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    result = await db.execute(select(Plan))
    return result.scalars().all()


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def super_create_plan(
    data: PlanCreate,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    # Planos do catálogo WR são globais (tenant_id NULL).
    plan = Plan(tenant_id=None, **data.model_dump())
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def super_get_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


@router.put("/plans/{plan_id}", response_model=PlanResponse)
async def super_update_plan(
    plan_id: UUID,
    data: PlanUpdate,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.commit()
    await db.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def super_delete_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    plan = await db.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    plan.is_active = False
    await db.commit()


# ------------------------------------------------------------------
# Assinaturas (lifecycle controlado pela WR)
# ------------------------------------------------------------------

@router.get("/subscriptions", response_model=list[TenantSubscriptionResponse])
async def super_list_subscriptions(
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    result = await db.execute(select(TenantSubscription))
    return result.scalars().all()


@router.post(
    "/subscriptions",
    response_model=TenantSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def super_create_subscription(
    data: TenantSubscriptionCreate,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    # Valida tenant e plano
    tenant = await db.get(Tenant, data.tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    plan = await db.get(Plan, data.plan_id)
    if not plan or not plan.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    subscription = TenantSubscription(
        tenant_id=data.tenant_id,
        plan_id=data.plan_id,
        status=data.status,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.get("/subscriptions/{subscription_id}", response_model=TenantSubscriptionResponse)
async def super_get_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    subscription = await db.get(TenantSubscription, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )
    return subscription


async def _load_subscription_and_plan(db: AsyncSession, subscription_id: UUID):
    stmt = (
        select(TenantSubscription, Plan)
        .join(Plan, TenantSubscription.plan_id == Plan.id)
        .where(TenantSubscription.id == subscription_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )
    subscription, plan = row
    await db.refresh(subscription)
    await db.refresh(plan)
    return subscription, plan


@router.post(
    "/subscriptions/{subscription_id}/activate",
    response_model=TenantSubscriptionResponse,
)
async def super_activate_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    subscription, plan = await _load_subscription_and_plan(db, subscription_id)
    start = utc_now()
    subscription.start_date = start
    subscription.end_date = _end_date_for_cycle(start, plan.billing_cycle)
    subscription.status = SubscriptionStatus.ACTIVE
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.post(
    "/subscriptions/{subscription_id}/suspend",
    response_model=TenantSubscriptionResponse,
)
async def super_suspend_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    subscription = await db.get(TenantSubscription, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )
    subscription.status = SubscriptionStatus.SUSPENDED
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.post(
    "/subscriptions/{subscription_id}/cancel",
    response_model=TenantSubscriptionResponse,
)
async def super_cancel_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    subscription = await db.get(TenantSubscription, subscription_id)
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found"
        )
    subscription.status = SubscriptionStatus.CANCELLED
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.post(
    "/subscriptions/{subscription_id}/renew",
    response_model=TenantSubscriptionResponse,
)
async def super_renew_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    subscription, plan = await _load_subscription_and_plan(db, subscription_id)
    if subscription.status not in (
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.TRIAL,
        SubscriptionStatus.PAST_DUE,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription cannot be renewed",
        )
    base = subscription.end_date or utc_now()
    subscription.end_date = _end_date_for_cycle(base, plan.billing_cycle)
    if subscription.status in (SubscriptionStatus.TRIAL, SubscriptionStatus.PAST_DUE):
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.start_date = subscription.start_date or utc_now()
    await db.commit()
    await db.refresh(subscription)
    return subscription


# ------------------------------------------------------------------
# Custom domain — confirmação manual (SUPER_ADMIN, desenvolvimento)
# ------------------------------------------------------------------

@router.post(
    "/tenants/{tenant_id}/custom-domain/confirm",
    response_model=CustomDomainOut,
)
async def super_confirm_custom_domain(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    """Confirmação manual de domínio por SUPER_ADMIN (dev sem DNS)."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if not tenant.custom_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No custom domain registered",
        )
    tenant.custom_domain_status = CustomDomainStatus.VERIFIED
    tenant.domain_verified_at = utc_now()
    tenant.domain_verification_error = None
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.post(
    "/tenants/{tenant_id}/custom-domain/activate",
    response_model=CustomDomainOut,
)
async def super_activate_custom_domain(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    """Ativa domínio customizado verificado (SUPER_ADMIN)."""
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if not tenant.custom_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No custom domain registered",
        )
    if tenant.custom_domain_status != CustomDomainStatus.VERIFIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain must be verified before activation",
        )
    tenant.custom_domain_status = CustomDomainStatus.ACTIVE
    await db.commit()
    await db.refresh(tenant)
    return tenant


# ------------------------------------------------------------------
# Tenant secrets — revelação de valor plano (SUPER_ADMIN)
# ------------------------------------------------------------------

@router.get(
    "/tenants/{tenant_id}/secrets/{secret_id}/reveal",
    response_model=TenantSecretReveal,
)
async def super_reveal_tenant_secret(
    tenant_id: UUID,
    secret_id: UUID,
    db: AsyncSession = Depends(get_db_privileged),
    current_user: dict = Depends(get_current_super_admin),
):
    """Revela o valor plano de um secret de tenant (SUPER_ADMIN)."""
    secret = await db.get(TenantSecret, secret_id)
    if not secret or secret.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found"
        )
    try:
        value = decrypt(secret.encrypted_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt secret",
        ) from exc
    return TenantSecretReveal(
        id=secret.id,
        tenant_id=secret.tenant_id,
        key=secret.key,
        value=value,
        description=secret.description,
        created_at=secret.created_at,
        updated_at=secret.updated_at,
    )
