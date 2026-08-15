from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.tenant import CustomDomainStatus, TenantStatus


class CustomDomainIn(BaseModel):
    custom_domain: str


class CustomDomainOut(BaseModel):
    id: UUID
    name: str
    slug: str
    custom_domain: str | None
    custom_domain_status: CustomDomainStatus = CustomDomainStatus.NONE
    domain_verification_token: str | None = None
    domain_verified_at: datetime | None = None
    domain_verification_error: str | None = None
    status: TenantStatus
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomDomainVerifyOut(CustomDomainOut):
    dns_instructions: dict | None = None
