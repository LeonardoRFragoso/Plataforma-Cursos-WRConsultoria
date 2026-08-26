"""Pydantic schemas for CourseMaterial."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


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


# ─── Presigned upload flow schemas ───

class CourseMaterialUploadUrlRequest(BaseModel):
    """Request body for POST /courses/{course_id}/materials/upload-url."""
    filename: str
    mime_type: str = "application/pdf"
    size_bytes: int
    sha256: str

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("filename cannot be empty")
        return v.strip()

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("sha256 must be a 64-character hex string")
        return v


class CourseMaterialUploadUrlResponse(BaseModel):
    """Response containing the presigned PUT URL and storage key."""
    upload_url: str
    storage_key: str
    expires_in: int


class CourseMaterialCompleteRequest(BaseModel):
    """Request body for POST /courses/{course_id}/materials/complete.

    Called by the client after successfully PUTting the file to the
    presigned URL. The backend verifies the object exists before
    creating the CourseMaterial record.
    """
    storage_key: str
    title: str
    mime_type: str = "application/pdf"
    size_bytes: int
    sha256: str
    document_type: str = "APOSTILA"

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("sha256 must be a 64-character hex string")
        return v
