from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime

class StudentBase(BaseModel):
    cpf: str
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

class StudentCreate(StudentBase):
    email: EmailStr
    full_name: str
    password: Optional[str] = None
    company_id: Optional[UUID] = None

class StudentUpdate(BaseModel):
    phone: Optional[str] = None
    company: Optional[str] = None
    company_id: Optional[UUID] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

class StudentResponse(StudentBase):
    id: UUID
    user_id: UUID
    email: Optional[str] = None
    full_name: Optional[str] = None
    temp_password: Optional[str] = None
    company_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
