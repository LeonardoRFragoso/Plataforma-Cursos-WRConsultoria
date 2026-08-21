from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompanyBase(BaseModel):
    legal_name: str = Field(..., min_length=2)
    trade_name: str | None = None
    cnpj: str = Field(..., min_length=14, max_length=18)
    rh_name: str | None = None
    rh_email: EmailStr | None = None
    rh_phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    legal_name: str | None = None
    trade_name: str | None = None
    cnpj: str | None = None
    rh_name: str | None = None
    rh_email: EmailStr | None = None
    rh_phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None


class CompanyResponse(CompanyBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
