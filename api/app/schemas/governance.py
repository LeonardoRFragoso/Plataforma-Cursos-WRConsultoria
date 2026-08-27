from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrivacyRequestCreate(BaseModel):
    request_type: str = Field(..., min_length=3, max_length=32)
    details: str | None = Field(default=None, max_length=4000)


class PrivacyRequestAdminUpdate(BaseModel):
    status: str = Field(..., min_length=3, max_length=32)
    admin_notes: str | None = Field(default=None, max_length=4000)


class PrivacyRequestResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    request_type: str
    status: str
    details: str | None
    admin_notes: str | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminAuditLogResponse(BaseModel):
    id: UUID
    actor_id: UUID
    actor_role: str
    method: str
    path: str
    status_code: int
    request_id: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
