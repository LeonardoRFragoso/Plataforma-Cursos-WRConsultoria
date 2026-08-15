from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.plan import BillingCycle


class PlanBase(BaseModel):
    name: str
    description: str | None = None
    price: float
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    features: dict | list = {}
    max_users: int | None = None
    max_courses: int | None = None
    is_active: bool = True


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    billing_cycle: BillingCycle | None = None
    features: dict | list | None = None
    max_users: int | None = None
    max_courses: int | None = None
    is_active: bool | None = None


class PlanResponse(PlanBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
