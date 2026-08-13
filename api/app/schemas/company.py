from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class CompanyBase(BaseModel):
    legal_name: str = Field(..., min_length=2)
    trade_name: Optional[str] = None
    cnpj: str = Field(..., min_length=14, max_length=18)
    rh_name: Optional[str] = None
    rh_email: Optional[EmailStr] = None
    rh_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    cnpj: Optional[str] = None
    rh_name: Optional[str] = None
    rh_email: Optional[EmailStr] = None
    rh_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None


class CompanyResponse(CompanyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
