import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class AdminAuditLog(Base):
    """Append-only audit metadata for authenticated administrative mutations.

    Request bodies are intentionally not stored. This prevents passwords,
    financial credentials, personal documents and other secrets from being
    copied into the audit trail. ``actor_id`` intentionally has no FK so audit
    evidence remains immutable even if the user account is later removed.
    """

    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("ix_admin_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_admin_audit_logs_actor_created", "actor_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    actor_role = Column(String(32), nullable=False)
    method = Column(String(12), nullable=False)
    path = Column(String(512), nullable=False)
    status_code = Column(Integer, nullable=False)
    request_id = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)


class PrivacyRequest(Base):
    """Data-subject request workflow without automatic destructive actions."""

    __tablename__ = "privacy_requests"
    __table_args__ = (
        Index("ix_privacy_requests_tenant_status", "tenant_id", "status"),
        Index("ix_privacy_requests_user_created", "user_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    request_type = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    details = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
