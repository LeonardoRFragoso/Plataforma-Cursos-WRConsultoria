from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.models.user import UserRole
import re

class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str
    cpf: Optional[str] = None

class UserLogin(BaseModel):
    identifier: str
    password: str
    
    @field_validator('identifier')
    @classmethod
    def validate_identifier(cls, v):
        if not v:
            raise ValueError('identifier cannot be empty')
        return v

class UserResponse(UserBase):
    id: UUID
    cpf: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str
