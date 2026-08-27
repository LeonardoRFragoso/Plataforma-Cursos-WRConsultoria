from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base
from app.core.utils import utc_now


class ComplianceStatus:
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    COMPLIANCE_READY = "COMPLIANCE_READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ARCHIVED = "ARCHIVED"


class PedagogicalProjectStatus:
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class ProfessionalAssignmentRole:
    INSTRUCTOR = "INSTRUCTOR"
    TECHNICAL_RESPONSIBLE = "TECHNICAL_RESPONSIBLE"


class TrainingProfessional(Base):
    __tablename__ = "training_professionals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cpf", name="uq_training_professional_tenant_cpf"),
        Index("ix_training_professionals_tenant_active", "tenant_id", "is_active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    cpf = Column(String(11), nullable=False, index=True)
    qualification = Column(Text, nullable=False)
    professional_registration = Column(String(128), nullable=True)
    council = Column(String(64), nullable=True)
    registration_state = Column(String(8), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class PedagogicalProjectVersion(Base):
    __tablename__ = "pedagogical_project_versions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "course_id",
            "version",
            name="uq_pedagogical_project_course_version",
        ),
        Index(
            "ix_pedagogical_projects_tenant_course_status",
            "tenant_id",
            "course_id",
            "status",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default=PedagogicalProjectStatus.DRAFT, index=True)
    general_objective = Column(Text, nullable=False)
    specific_objectives = Column(JSONB, nullable=False, default=list)
    target_audience = Column(Text, nullable=False)
    teaching_strategy = Column(Text, nullable=False)
    syllabus = Column(JSONB, nullable=False, default=list)
    workload_hours = Column(Float, nullable=False)
    delivery_mode = Column(String(32), nullable=False)
    materials = Column(JSONB, nullable=False, default=list)
    assessment_methodology = Column(Text, nullable=False)
    approval_notes = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CourseComplianceProfile(Base):
    __tablename__ = "course_compliance_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "course_id", name="uq_course_compliance_tenant_course"),
        Index("ix_course_compliance_tenant_status", "tenant_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    regulatory_standard = Column(String(64), nullable=False)
    regulatory_version = Column(String(128), nullable=False)
    delivery_mode = Column(String(32), nullable=False)
    requires_practical_component = Column(Boolean, nullable=False, default=False)
    requires_final_assessment = Column(Boolean, nullable=False, default=True)
    minimum_score = Column(Float, nullable=True)
    validity_period_months = Column(Integer, nullable=True)
    prerequisites = Column(Text, nullable=True)
    certificate_required_fields = Column(JSONB, nullable=False, default=list)
    technical_responsible_id = Column(
        UUID(as_uuid=True),
        ForeignKey("training_professionals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pedagogical_project_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pedagogical_project_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_compliance_review_at = Column(DateTime, nullable=True)
    next_compliance_review_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default=ComplianceStatus.DRAFT, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CourseTrainingProfessional(Base):
    __tablename__ = "course_training_professionals"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "course_id",
            "professional_id",
            "role",
            name="uq_course_training_professional_role",
        ),
        Index("ix_course_training_professionals_tenant_course", "tenant_id", "course_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    professional_id = Column(
        UUID(as_uuid=True),
        ForeignKey("training_professionals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
