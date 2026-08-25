import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        Index(
            "uq_certificate_active_per_enrollment",
            "enrollment_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False, index=True)
    certificate_number = Column(String, unique=True, index=True, nullable=False)
    issued_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    status = Column(String, nullable=False, default="ACTIVE", index=True)
    version = Column(Integer, nullable=False, default=1)
    supersedes_id = Column(UUID(as_uuid=True), ForeignKey("certificates.id"), nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revocation_reason = Column(Text, nullable=True)
    content_hash = Column(String, nullable=True, index=True)
    pdf_path = Column(String, nullable=True)
    validation_code = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CertificateEvent(Base):
    __tablename__ = "certificate_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    certificate_id = Column(UUID(as_uuid=True), ForeignKey("certificates.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
