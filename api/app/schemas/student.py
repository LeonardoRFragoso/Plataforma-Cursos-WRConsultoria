from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class StudentBase(BaseModel):
    cpf: str
    phone: str | None = None
    company: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None

class StudentCreate(StudentBase):
    email: EmailStr
    full_name: str
    password: str | None = None
    company_id: UUID | None = None

class StudentUpdate(BaseModel):
    phone: str | None = None
    company: str | None = None
    company_id: UUID | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None

class StudentResponse(StudentBase):
    id: UUID
    user_id: UUID
    email: str | None = None
    full_name: str | None = None
    temp_password: str | None = None
    company_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
