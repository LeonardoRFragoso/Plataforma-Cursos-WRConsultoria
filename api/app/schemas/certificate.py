from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CertificateCreate(BaseModel):
    enrollment_id: UUID


class CertificateResponse(BaseModel):
    id: UUID
    enrollment_id: UUID
    certificate_number: str
    validation_code: str
    issued_at: datetime
    expires_at: datetime | None = None
    status: str = "ACTIVE"
    version: int = 1
    supersedes_id: UUID | None = None
    revoked_at: datetime | None = None
    revoked_by: UUID | None = None
    revocation_reason: str | None = None
    content_hash: str | None = None
    pdf_path: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudentCertificateResponse(BaseModel):
    id: UUID
    enrollment_id: UUID
    certificate_number: str
    validation_code: str
    issued_at: datetime
    expires_at: datetime | None = None
    status: str = "ACTIVE"
    version: int = 1
    revocation_reason: str | None = None
    course_id: UUID
    course_name: str
    course_code: str | None = None
    course_category: str | None = None
    cover_image_url: str | None = None
    cover_image_alt: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateValidationRequest(BaseModel):
    validation_code: str


class CertificateValidationResponse(BaseModel):
    valid: bool
    status: str | None = None
    certificate_number: str | None = None
    validation_code: str | None = None
    version: int | None = None
    student_name: str | None = None
    course_name: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    content_hash: str | None = None


class CertificateRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)


class CertificateReissueRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=2000)


class CertificateEventResponse(BaseModel):
    id: UUID
    certificate_id: UUID
    event_type: str
    actor_id: UUID | None = None
    reason: str | None = None
    details: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
