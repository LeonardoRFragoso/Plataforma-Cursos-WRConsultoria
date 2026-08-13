from pydantic import BaseModel
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
    user_id: UUID

class StudentUpdate(BaseModel):
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None

class StudentResponse(StudentBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
