import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base
from app.core.utils import utc_now


class TrainingProfessional(Base):
    __tablename__ = "training_professionals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "cpf", name="uq_training_professional_tenant_cpf"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    full_name = Column(String, nullable=False)
    cpf = Column(String, nullable=True)
    professional_role = Column(String, nullable=False)  # INSTRUCTOR | TECHNICAL_RESPONSIBLE
    qualification = Column(Text, nullable=False)
    professional_council = Column(String, nullable=True)
    registration_number = Column(String, nullable=True)
    proficiency_evidence = Column(Text, nullable=True)
    signature_method = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
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
    version = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="DRAFT", index=True)  # DRAFT | APPROVED | SUPERSEDED
    general_objective = Column(Text, nullable=True)
    safety_principles = Column(Text, nullable=True)
    pedagogical_strategy = Column(Text, nullable=True)
    operational_infrastructure = Column(Text, nullable=True)
    theoretical_program = Column(JSONB, nullable=False, default=list)
    practical_program = Column(JSONB, nullable=False, default=list)
    module_objectives = Column(JSONB, nullable=False, default=list)
    workload_hours = Column(Float, nullable=True)
    minimum_daily_dedication_minutes = Column(Integer, nullable=True)
    maximum_completion_days = Column(Integer, nullable=True)
    target_audience = Column(Text, nullable=True)
    teaching_materials = Column(JSONB, nullable=False, default=list)
    learning_tools = Column(JSONB, nullable=False, default=list)
    assessment_methodology = Column(Text, nullable=True)
    support_channel = Column(Text, nullable=True)
    normative_reference = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CourseComplianceProfile(Base):
    __tablename__ = "course_compliance_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "course_id", name="uq_course_compliance_tenant_course"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    regulatory_standard = Column(String, nullable=True, index=True)
    regulatory_version = Column(Text, nullable=True)
    normative_source_url = Column(Text, nullable=True)
    source_checked_at = Column(DateTime, nullable=True)
    required_delivery_mode = Column(String, nullable=True)  # EAD | SEMIPRESENCIAL | PRESENCIAL
    requires_practical_component = Column(Boolean, nullable=False, default=False)
    practical_minimum_percent = Column(Float, nullable=True)
    requires_final_assessment = Column(Boolean, nullable=False, default=False)
    assessment_practical_scenarios_validated = Column(Boolean, nullable=False, default=False)
    minimum_score = Column(Float, nullable=True)
    minimum_workload_hours = Column(Float, nullable=True)
    periodicity_months = Column(Integer, nullable=True)
    prerequisites = Column(Text, nullable=True)
    technical_responsible_id = Column(
        UUID(as_uuid=True), ForeignKey("training_professionals.id"), nullable=True
    )
    pedagogical_project_version_id = Column(
        UUID(as_uuid=True), ForeignKey("pedagogical_project_versions.id"), nullable=True
    )
    support_channel_verified = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="REVIEW_REQUIRED", index=True)
    blocker_reason = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    next_review_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CourseTrainingProfessional(Base):
    __tablename__ = "course_training_professionals"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "course_id", "professional_id", "role", name="uq_course_training_professional"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    professional_id = Column(
        UUID(as_uuid=True), ForeignKey("training_professionals.id"), nullable=False, index=True
    )
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class PracticalTrainingRecord(Base):
    __tablename__ = "practical_training_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    instructor_id = Column(
        UUID(as_uuid=True), ForeignKey("training_professionals.id"), nullable=False
    )
    occurred_at = Column(DateTime, nullable=False)
    location = Column(Text, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    practical_percent = Column(Float, nullable=True)
    result = Column(String, nullable=False)  # SATISFATORIO | INSATISFATORIO
    notes = Column(Text, nullable=True)
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=utc_now, nullable=False)
    last_heartbeat_at = Column(DateTime, default=utc_now, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    active_seconds = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class TrainingAccessEvent(Base):
    __tablename__ = "training_access_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    event_data = Column(JSONB, nullable=False, default=dict)
    session_id = Column(UUID(as_uuid=True), ForeignKey("training_sessions.id"), nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    occurred_at = Column(DateTime, default=utc_now, nullable=False, index=True)
    retain_until = Column(DateTime, nullable=True, index=True)
