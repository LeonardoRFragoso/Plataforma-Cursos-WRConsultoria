from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class ProfessionalEvidenceType:
    LEGAL_QUALIFICATION = "LEGAL_QUALIFICATION"
    PROFESSIONAL_REGISTRATION = "PROFESSIONAL_REGISTRATION"
    PROFICIENCY = "PROFICIENCY"
    EXPERIENCE = "EXPERIENCE"
    TRAINING_CERTIFICATE = "TRAINING_CERTIFICATE"
    OTHER = "OTHER"

    ALL = {
        LEGAL_QUALIFICATION,
        PROFESSIONAL_REGISTRATION,
        PROFICIENCY,
        EXPERIENCE,
        TRAINING_CERTIFICATE,
        OTHER,
    }


class ProfessionalEvidenceStatus:
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

    ALL = {PENDING, VERIFIED, REJECTED}


class TrainingProfessionalEvidence(Base):
    """Auditable evidence supporting a training professional's qualification.

    This table stores metadata/references only. Raw documents belong in the
    platform's controlled object storage and private keys/PFX material must
    never be stored here.
    """

    __tablename__ = "training_professional_evidence"
    __table_args__ = (
        Index(
            "ix_training_professional_evidence_tenant_professional",
            "tenant_id",
            "professional_id",
        ),
        Index(
            "ix_training_professional_evidence_tenant_type_status",
            "tenant_id",
            "evidence_type",
            "status",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    professional_id = Column(
        UUID(as_uuid=True),
        ForeignKey("training_professionals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    evidence_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default=ProfessionalEvidenceStatus.PENDING, index=True)
    document_reference = Column(String(1024), nullable=True)
    document_sha256 = Column(String(64), nullable=True)
    issuer = Column(String(255), nullable=True)
    reference_number = Column(String(255), nullable=True)
    issued_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
