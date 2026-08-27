from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class RetentionPolicyStatus:
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"


class ComplianceRetentionPolicyVersion(Base):
    """Versioned retention governance; it never performs deletion by itself."""

    __tablename__ = "compliance_retention_policy_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_compliance_retention_policy_version"),
        Index("ix_compliance_retention_tenant_status", "tenant_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default=RetentionPolicyStatus.DRAFT, index=True)

    certificate_retention_days = Column(Integer, nullable=True)
    assessment_retention_days = Column(Integer, nullable=True)
    training_event_retention_days = Column(Integer, nullable=True)
    student_confirmation_retention_days = Column(Integer, nullable=True)
    practical_evidence_retention_days = Column(Integer, nullable=True)

    legal_basis = Column(Text, nullable=True)
    purpose = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
