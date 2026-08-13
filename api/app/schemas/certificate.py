from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class CertificateCreate(BaseModel):
    enrollment_id: UUID

class CertificateResponse(BaseModel):
    id: UUID
    enrollment_id: UUID
    certificate_number: str
    validation_code: str
    issued_at: datetime
    pdf_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CertificateValidationRequest(BaseModel):
    validation_code: str

class CertificateValidationResponse(BaseModel):
    valid: bool
    certificate_number: Optional[str] = None
    student_name: Optional[str] = None
    course_name: Optional[str] = None
    issued_at: Optional[datetime] = None
