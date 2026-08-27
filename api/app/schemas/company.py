from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.normalization import validate_cnpj


class CompanyBase(BaseModel):
    legal_name: str = Field(..., min_length=2)
    trade_name: str | None = None
    cnpj: str = Field(..., min_length=14, max_length=18)
    rh_name: str | None = None
    rh_email: EmailStr | None = None
    rh_phone: str | None = None
    billing_email: EmailStr | None = None
    contract_reference: str | None = None
    status: str = "ACTIVE"
    notes: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None

    @field_validator("cnpj")
    @classmethod
    def validate_company_cnpj(cls, value: str) -> str:
        return validate_cnpj(value)


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    legal_name: str | None = None
    trade_name: str | None = None
    cnpj: str | None = None
    rh_name: str | None = None
    rh_email: EmailStr | None = None
    rh_phone: str | None = None
    billing_email: EmailStr | None = None
    contract_reference: str | None = None
    status: str | None = None
    notes: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None

    @field_validator("cnpj")
    @classmethod
    def validate_company_cnpj(cls, value: str | None) -> str | None:
        return validate_cnpj(value) if value else value


class CompanyResponse(CompanyBase):
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
