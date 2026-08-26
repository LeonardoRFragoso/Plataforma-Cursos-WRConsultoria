"""Pydantic schemas for CourseMaterial."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CourseMaterialBase(BaseModel):
    title: str
    document_type: str = "APOSTILA"
    is_active: bool = True


class CourseMaterialCreate(CourseMaterialBase):
    course_id: UUID
    storage_key: str
    mime_type: str = "application/pdf"
    size_bytes: int | None = None
    sha256: str | None = None


class CourseMaterialUpdate(BaseModel):
    title: str | None = None
    document_type: str | None = None
    is_active: bool | None = None


class CourseMaterialResponse(CourseMaterialBase):
    id: UUID
    course_id: UUID
    storage_key: str
    mime_type: str
    size_bytes: int | None = None
    sha256: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
