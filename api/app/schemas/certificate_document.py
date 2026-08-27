from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CertificateDocumentResponse(BaseModel):
    id: UUID
    certificate_id: UUID
    enrollment_id: UUID
    status: str
    snapshot_version: str
    snapshot_sha256: str
    original_pdf_sha256: str
    original_size_bytes: int
    rendered_at: datetime
    signed_pdf_sha256: str | None = None
    signed_size_bytes: int | None = None
    signature_provider: str | None = None
    signed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CertificateDocumentPrepareResponse(BaseModel):
    certificate_id: UUID
    certificate_number: str
    validation_code: str
    certificate_status: str
    document: CertificateDocumentResponse
    created: bool


class CertificateDocumentIntegrityResponse(BaseModel):
    certificate_id: UUID
    document_status: str
    artifact: str
    valid: bool
    expected_sha256: str
    actual_sha256: str
    size_bytes: int
    checked_at: datetime


class CertificateDocumentSnapshotResponse(BaseModel):
    certificate_id: UUID
    snapshot_version: str
    snapshot_sha256: str
    snapshot: dict
