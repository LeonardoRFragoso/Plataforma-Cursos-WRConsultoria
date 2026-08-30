from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.professional_evidence import ProfessionalEvidenceStatus, ProfessionalEvidenceType


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ProfessionalEvidenceCreate(BaseModel):
    evidence_type: str
    document_reference: str | None = Field(default=None, max_length=1024)
    document_sha256: str | None = None
    issuer: str | None = Field(default=None, max_length=255)
    reference_number: str | None = Field(default=None, max_length=255)
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("evidence_type")
    @classmethod
    def validate_evidence_type(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in ProfessionalEvidenceType.ALL:
            raise ValueError(
                "Invalid evidence_type. Allowed: "
                + ", ".join(sorted(ProfessionalEvidenceType.ALL))
            )
        return normalized

    @field_validator("document_sha256")
    @classmethod
    def validate_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not _SHA256_RE.fullmatch(normalized):
            raise ValueError("document_sha256 must be a 64-character hexadecimal SHA-256 digest")
        return normalized


class ProfessionalEvidenceDecision(BaseModel):
    status: str
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {
            ProfessionalEvidenceStatus.VERIFIED,
            ProfessionalEvidenceStatus.REJECTED,
        }:
            raise ValueError("status must be VERIFIED or REJECTED")
        return normalized


class ProfessionalEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    professional_id: UUID
    evidence_type: str
    status: str
    document_reference: str | None
    document_sha256: str | None
    issuer: str | None
    reference_number: str | None
    issued_at: datetime | None
    expires_at: datetime | None
    verified_at: datetime | None
    verified_by: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
