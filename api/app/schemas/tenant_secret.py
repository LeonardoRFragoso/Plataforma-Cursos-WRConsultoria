from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantSecretCreate(BaseModel):
    key: str
    value: str
    description: str | None = None


class TenantSecretUpdate(BaseModel):
    value: str
    description: str | None = None


class TenantSecretResponse(BaseModel):
    """Resposta nunca expõe o valor plano, apenas metadados."""

    id: UUID
    tenant_id: UUID
    key: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TenantSecretReveal(BaseModel):
    """Resposta com valor plano — apenas para super_admin."""

    id: UUID
    tenant_id: UUID
    key: str
    value: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
