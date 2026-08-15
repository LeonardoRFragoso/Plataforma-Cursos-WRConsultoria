from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.tenant import TenantStatus


class CustomDomainIn(BaseModel):
    custom_domain: str


class CustomDomainOut(BaseModel):
    id: UUID
    name: str
    slug: str
    custom_domain: str | None
    status: TenantStatus
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
