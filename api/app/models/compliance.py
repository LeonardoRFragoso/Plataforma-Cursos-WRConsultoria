import uuid
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base
from app.core.utils import utc_now


class ComplianceStatus(str, PyEnum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    COMPLIANCE_READY = "COMPLIANCE_READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ARCHIVED = "ARCHIVED"


class PedagogicalProjectStatus(str, PyEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class ProfessionalRole(str, PyEnum):
    INSTRUCTOR = "INSTRUCTOR"
    TECHNICAL_RESPONSIBLE = "TECHNICAL_RESPONSIBLE"


class PracticalResult(str, PyEnum):
    SATISFATORIO = "SATISFATORIO"
    INSATISFATORIO = "INSATISFATORIO"


class TrainingProfessional(Base):
    __tablename__ = "training_professionals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cpf", name="uq_training_professional_tenant_cpf"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    full_name = Column(String, nullable=False)
    cpf = Column(String(11), nullable=False)
    qualification = Column(Text, nullable=False)
    professional_council = Column(String, nullable=True)
    registration_number = Column(String, nullable=True)
    registration_state = Column(String(2), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    signature_method = Column(String, nullable=True)
    signature_reference = Column(String, nullable=True)
    signature_verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class PedagogicalProjectVersion(Base):
    __tablename__ = "pedagogical_project_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "course_id", "version", name="uq_pedagogical_project_course_version"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default=PedagogicalProjectStatus.DRAFT.value, index=True)
    general_objective = Column(Text, nullable=False)
    principles_and_concepts = Column(Text, nullable=False)
    pedagogical_strategy = Column(Text, nullable=False)
    support_infrastructure = Column(Text, nullable=False)
    theoretical_program = Column(JSONB, nullable=False, default=list)
    practical_program = Column(JSONB, nullable=False, default=list)
    module_objectives = Column(JSONB, nullable=False, default=list)
    workload_hours = Column(Integer, nullable=False)
    minimum_daily_dedication_minutes = Column(Integer, nullable=False)
    maximum_completion_days = Column(Integer, nullable=False)
    target_audience = Column(Text, nullable=False)
    didactic_materials = Column(JSONB, nullable=False, default=list)
    learning_tools = Column(JSONB, nullable=False, default=list)
    assessment_methodology = Column(Text, nullable=False)
    practical_strategy = Column(Text, nullable=True)
    normative_reference = Column(Text, nullable=False)
    technical_responsible_id = Column(UUID(as_uuid=True), ForeignKey("training_professionals.id"), nullable=False)
    approved_at = Column(DateTime, nullable=True)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    valid_until = Column(Date, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CourseProfessionalAssignment(Base):
    __tablename__ = "course_professional_assignments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "course_id", "pedagogical_project_version_id", "professional_id", "role",
            name="uq_course_professional_assignment",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    pedagogical_project_version_id = Column(
        UUID(as_uuid=True), ForeignKey("pedagogical_project_versions.id"), nullable=False, index=True
    )
    professional_id = Column(UUID(as_uuid=True), ForeignKey("training_professionals.id"), nullable=False, index=True)
    role = Column(String, nullable=False, index=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class CourseComplianceProfile(Base):
    __tablename__ = "course_compliance_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "course_id", name="uq_course_compliance_profile"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    regulatory_standard = Column(String, nullable=False)
    regulatory_version = Column(String, nullable=False)
    regulatory_source_url = Column(Text, nullable=False)
    regulatory_effective_from = Column(Date, nullable=True)
    delivery_mode = Column(String, nullable=False)
    requires_practical_component = Column(Boolean, nullable=False, default=False)
    practical_component_description = Column(Text, nullable=True)
    requires_final_assessment = Column(Boolean, nullable=False, default=True)
    minimum_score = Column(Float, nullable=False, default=60.0)
    validity_period_months = Column(Integer, nullable=True)
    recycling_rule = Column(Text, nullable=True)
    regulatory_prerequisites = Column(Text, nullable=True)
    certificate_required_fields = Column(JSONB, nullable=False, default=list)
    practical_scenario_question_count = Column(Integer, nullable=False, default=1)
    access_log_retention_months_after_validity = Column(Integer, nullable=False, default=24)
    pedagogical_project_version_id = Column(
        UUID(as_uuid=True), ForeignKey("pedagogical_project_versions.id"), nullable=True, index=True
    )
    technical_responsible_id = Column(
        UUID(as_uuid=True), ForeignKey("training_professionals.id"), nullable=True, index=True
    )
    last_compliance_review_at = Column(DateTime, nullable=True)
    next_compliance_review_at = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default=ComplianceStatus.DRAFT.value, index=True)
    review_notes = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by_professional_id = Column(
        UUID(as_uuid=True), ForeignKey("training_professionals.id"), nullable=True
    )
    official_issuance_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class PracticalCompletionEvidence(Base):
    __tablename__ = "practical_completion_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    professional_id = Column(UUID(as_uuid=True), ForeignKey("training_professionals.id"), nullable=False)
    occurred_on = Column(Date, nullable=False)
    location = Column(String, nullable=False)
    result = Column(String, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    recorded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class TrainingAccessLog(Base):
    __tablename__ = "training_access_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=True, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    session_id = Column(String(128), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    event_metadata = Column(JSONB, nullable=True)
    occurred_at = Column(DateTime, default=utc_now, nullable=False, index=True)
    retention_until = Column(Date, nullable=True, index=True)
