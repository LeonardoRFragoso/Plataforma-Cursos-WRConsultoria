from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base
from app.core.utils import utc_now


class CertificateDocumentStatus:
    PENDING_SIGNATURE = "PENDING_SIGNATURE"
    SIGNED = "SIGNED"


class CertificateDocument(Base):
    """Immutable regulatory certificate artifact metadata.

    The certificate registry row and the document artifact intentionally have
    separate lifecycles. A certificate may be PENDING_SIGNATURE while this row
    already preserves the exact snapshot and original PDF bytes that were sent
    to a signing provider. Once SIGNED, the database trigger installed by the
    migration prevents any further mutation.
    """

    __tablename__ = "certificate_documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "certificate_id",
            name="uq_certificate_document_tenant_certificate",
        ),
        Index(
            "ix_certificate_documents_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_certificate_documents_tenant_enrollment",
            "tenant_id",
            "enrollment_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    certificate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("certificates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    enrollment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("enrollments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        nullable=False,
        default=CertificateDocumentStatus.PENDING_SIGNATURE,
        index=True,
    )

    snapshot_version = Column(String(16), nullable=False, default="1")
    snapshot = Column(JSONB, nullable=False)
    snapshot_sha256 = Column(String(64), nullable=False, index=True)

    # Exact PDF bytes prepared for the signer. These fields never change.
    original_storage_key = Column(String(1024), nullable=False)
    original_pdf_sha256 = Column(String(64), nullable=False, index=True)
    original_size_bytes = Column(Integer, nullable=False)
    rendered_at = Column(DateTime, nullable=False, default=utc_now)

    # Filled exactly once by the future signing-provider adapter.
    signed_storage_key = Column(String(1024), nullable=True)
    signed_pdf_sha256 = Column(String(64), nullable=True, index=True)
    signed_size_bytes = Column(Integer, nullable=True)
    signature_provider = Column(String(128), nullable=True)
    signature_metadata = Column(JSONB, nullable=False, default=dict)
    signed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
