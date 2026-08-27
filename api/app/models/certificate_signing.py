from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base
from app.core.utils import utc_now


class SigningJobStatus:
    QUEUED = "QUEUED"
    SUBMITTING = "SUBMITTING"
    WAITING_PROVIDER = "WAITING_PROVIDER"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    SIGNED = "SIGNED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    TERMINAL = {SIGNED, FAILED, CANCELLED}
    PROCESSABLE = {QUEUED, WAITING_PROVIDER, RETRY_SCHEDULED}


class CertificateSigningProfile(Base):
    """Tenant signing policy and public certificate metadata.

    Private keys/PFX contents never belong here. ``key_reference`` may point
    to an external HSM/KMS/provider key identifier, but must not contain key
    material. Provider credentials are stored separately in encrypted
    TenantSecret records.
    """

    __tablename__ = "certificate_signing_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_certificate_signing_profile_tenant"),
        Index("ix_certificate_signing_profiles_tenant_enabled", "tenant_id", "enabled"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    provider = Column(String(64), nullable=False, default="DISABLED")
    enabled = Column(Boolean, nullable=False, default=False)
    signer_display_name = Column(String(255), nullable=False)
    signer_identifier = Column(String(128), nullable=True)
    certificate_fingerprint_sha256 = Column(String(64), nullable=True, index=True)
    certificate_serial = Column(String(256), nullable=True)
    certificate_subject = Column(Text, nullable=True)
    certificate_issuer = Column(Text, nullable=True)
    certificate_not_before = Column(DateTime, nullable=True)
    certificate_not_after = Column(DateTime, nullable=True, index=True)
    key_reference = Column(String(512), nullable=True)
    provider_metadata = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CertificateSigningJob(Base):
    __tablename__ = "certificate_signing_jobs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "document_id",
            name="uq_certificate_signing_job_tenant_document",
        ),
        Index("ix_certificate_signing_jobs_tenant_status_next", "tenant_id", "status", "next_attempt_at"),
        Index("ix_certificate_signing_jobs_provider_job", "provider", "provider_job_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("certificate_documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    certificate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("certificates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("certificate_signing_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider = Column(String(64), nullable=False, index=True)
    profile_snapshot = Column(JSONB, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default=SigningJobStatus.QUEUED, index=True)
    provider_job_id = Column(String(512), nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    next_attempt_at = Column(DateTime, nullable=True, index=True)
    last_attempt_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    last_error_code = Column(String(128), nullable=True)
    last_error_message = Column(Text, nullable=True)
    result_metadata = Column(JSONB, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CertificateSigningEvent(Base):
    __tablename__ = "certificate_signing_events"
    __table_args__ = (
        Index("ix_certificate_signing_events_tenant_job_created", "tenant_id", "job_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("certificate_signing_jobs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(64), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    details = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now, nullable=False)
