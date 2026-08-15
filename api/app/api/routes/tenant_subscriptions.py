"""Assinaturas SaaS — acesso somente leitura para tenant admin.

O lifecycle administrativo (criar/ativar/suspender/cancelar/renovar) é
controlado pela WR via endpoints de SUPER_ADMIN em
``app.api.routes.super_admin``. O admin do tenant pode apenas consultar
suas próprias assinaturas.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.models.tenant_subscription import TenantSubscription
from app.schemas.tenant_subscription import TenantSubscriptionResponse

router = APIRouter()


@router.get("/", response_model=list[TenantSubscriptionResponse])
async def list_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Lista as assinaturas do tenant atual (somente leitura)."""
    tenant_id = get_current_tenant_id()
    stmt = select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/current", response_model=TenantSubscriptionResponse | None)
async def get_current_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Retorna a assinatura ativa/vigente do tenant atual."""
    tenant_id = get_current_tenant_id()
    stmt = (
        select(TenantSubscription)
        .where(TenantSubscription.tenant_id == tenant_id)
        .order_by(TenantSubscription.created_at.desc())
    )
    result = await db.execute(stmt)
    subscription = result.scalars().first()
    return subscription


@router.get("/{subscription_id}", response_model=TenantSubscriptionResponse)
async def get_subscription(
    subscription_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Consulta uma assinatura do próprio tenant (escopo tenant)."""
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
