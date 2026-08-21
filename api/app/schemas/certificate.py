from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CertificateCreate(BaseModel):
    enrollment_id: UUID

class CertificateResponse(BaseModel):
    id: UUID
    enrollment_id: UUID
    certificate_number: str
    validation_code: str
    issued_at: datetime
    pdf_path: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StudentCertificateResponse(BaseModel):
    """Certificate with joined course context for the authenticated student.

    Used by GET /certificates/me so the student Certificates page can render
    course identity without a second round-trip per certificate.
    """

    id: UUID
    enrollment_id: UUID
    certificate_number: str
    validation_code: str
    issued_at: datetime
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
    certificate_number: str | None = None
    student_name: str | None = None
    course_name: str | None = None
    issued_at: datetime | None = None
