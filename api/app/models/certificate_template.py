from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base
from app.core.utils import utc_now


class CertificateTemplateVersionStatus:
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class CertificateTemplate(Base):
    __tablename__ = "certificate_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_certificate_template_tenant_slug"),
        Index("ix_certificate_templates_tenant_active", "tenant_id", "is_active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(96), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CertificateTemplateVersion(Base):
    __tablename__ = "certificate_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "template_id",
            "version",
            name="uq_certificate_template_version_number",
        ),
        Index(
            "ix_certificate_template_versions_tenant_template_status",
            "tenant_id",
            "template_id",
            "status",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("certificate_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default=CertificateTemplateVersionStatus.DRAFT, index=True)
    visual_config = Column(JSONB, nullable=False, default=dict)
    published_at = Column(DateTime, nullable=True)
    published_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CourseCertificateTemplateAssignment(Base):
    __tablename__ = "course_certificate_template_assignments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "course_id",
            name="uq_course_certificate_template_assignment",
        ),
        Index("ix_course_certificate_template_tenant_template", "tenant_id", "template_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False, index=True)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("certificate_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, default=utc_now, nullable=False)
