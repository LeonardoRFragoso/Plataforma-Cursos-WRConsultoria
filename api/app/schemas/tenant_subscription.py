from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.tenant_subscription import SubscriptionStatus


class TenantSubscriptionBase(BaseModel):
    plan_id: UUID


class TenantSubscriptionCreate(TenantSubscriptionBase):
    """Criação de assinatura pelo SUPER_ADMIN (atribui plano a um tenant)."""

    tenant_id: UUID
    status: SubscriptionStatus = SubscriptionStatus.TRIAL


class TenantSubscriptionUpdate(BaseModel):
    status: SubscriptionStatus | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class TenantSubscriptionResponse(TenantSubscriptionBase):
    id: UUID
    tenant_id: UUID
    status: SubscriptionStatus
    start_date: datetime | None = None
    end_date: datetime | None = None
    mercado_pago_id: str | None = None
    external_reference: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
