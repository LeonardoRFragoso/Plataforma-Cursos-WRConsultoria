from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
from app.models.plan import BillingCycle, Plan
from app.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from app.schemas.tenant_subscription import (
    TenantSubscriptionCreate,
    TenantSubscriptionResponse,
    TenantSubscriptionUpdate,
)

router = APIRouter()


def _end_date_for_cycle(start: datetime, billing_cycle: str):
    if billing_cycle == BillingCycle.MONTHLY:
        return start + timedelta(days=30)
    if billing_cycle == BillingCycle.YEARLY:
        return start + timedelta(days=365)
    return None


@router.get("/", response_model=list[TenantSubscriptionResponse])
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=TenantSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    data: TenantSubscriptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()

    plan = await db.get(Plan, data.plan_id)
    if not plan or plan.tenant_id != tenant_id or not plan.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    subscription = TenantSubscription(
        tenant_id=tenant_id,
        plan_id=data.plan_id,
        status=SubscriptionStatus.PENDENTE,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.get("/{subscription_id}", response_model=TenantSubscriptionResponse)
async def get_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(TenantSubscription).where(
        TenantSubscription.id == subscription_id,
        TenantSubscription.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )
    return subscription


@router.put("/{subscription_id}", response_model=TenantSubscriptionResponse)
async def update_subscription(
    subscription_id: UUID,
    data: TenantSubscriptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(TenantSubscription).where(
        TenantSubscription.id == subscription_id,
        TenantSubscription.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(subscription, field, value)

    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.post("/{subscription_id}/activate", response_model=TenantSubscriptionResponse)
async def activate_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = (
        select(TenantSubscription, Plan)
        .join(Plan, TenantSubscription.plan_id == Plan.id)
        .where(
            TenantSubscription.id == subscription_id,
            TenantSubscription.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    subscription, plan = row
    await db.refresh(subscription)
    await db.refresh(plan)
    start = utc_now()
    subscription.start_date = start
    subscription.end_date = _end_date_for_cycle(start, plan.billing_cycle)
    subscription.status = SubscriptionStatus.ATIVO
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.post("/{subscription_id}/cancel", response_model=TenantSubscriptionResponse)
async def cancel_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = select(TenantSubscription).where(
        TenantSubscription.id == subscription_id,
        TenantSubscription.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    subscription.status = SubscriptionStatus.CANCELADO
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.post("/{subscription_id}/renew", response_model=TenantSubscriptionResponse)
async def renew_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    stmt = (
        select(TenantSubscription, Plan)
        .join(Plan, TenantSubscription.plan_id == Plan.id)
        .where(
            TenantSubscription.id == subscription_id,
            TenantSubscription.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found",
        )

    subscription, plan = row
    await db.refresh(subscription)
    await db.refresh(plan)
    if subscription.status not in (SubscriptionStatus.ATIVO, SubscriptionStatus.PENDENTE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription cannot be renewed",
        )

    base = subscription.end_date or utc_now()
    subscription.end_date = _end_date_for_cycle(base, plan.billing_cycle)
    if subscription.status == SubscriptionStatus.PENDENTE:
        subscription.status = SubscriptionStatus.ATIVO
        subscription.start_date = subscription.start_date or utc_now()
    await db.commit()
    await db.refresh(subscription)
    return subscription
