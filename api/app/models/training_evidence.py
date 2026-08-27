from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base
from app.core.utils import utc_now


class RegulatoryCompletionState:
    ENROLLED = "ENROLLED"
    IN_PROGRESS = "IN_PROGRESS"
    CONTENT_COMPLETED = "CONTENT_COMPLETED"
    ASSESSMENT_PENDING = "ASSESSMENT_PENDING"
    ASSESSMENT_UNSATISFACTORY = "ASSESSMENT_UNSATISFACTORY"
    ASSESSMENT_SATISFACTORY = "ASSESSMENT_SATISFACTORY"
    PRACTICAL_COMPONENT_PENDING = "PRACTICAL_COMPONENT_PENDING"
    STUDENT_CONFIRMATION_PENDING = "STUDENT_CONFIRMATION_PENDING"
    CERTIFICATE_PENDING_SIGNATURE = "CERTIFICATE_PENDING_SIGNATURE"
    CERTIFIED = "CERTIFIED"
    COMPLIANCE_REVIEW_REQUIRED = "COMPLIANCE_REVIEW_REQUIRED"
    CANCELLED = "CANCELLED"
    NOT_REGULATORY = "NOT_REGULATORY"


class PracticalResult:
    PENDING = "PENDING"
    SATISFACTORY = "SATISFACTORY"
    UNSATISFACTORY = "UNSATISFACTORY"


class TrainingEventType:
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_ENDED = "SESSION_ENDED"
    LESSON_OPENED = "LESSON_OPENED"
    PROGRESS_UPDATED = "PROGRESS_UPDATED"
    LESSON_COMPLETED = "LESSON_COMPLETED"
    ASSESSMENT_STARTED = "ASSESSMENT_STARTED"
    ASSESSMENT_SUBMITTED = "ASSESSMENT_SUBMITTED"
    PRACTICAL_COMPONENT_RECORDED = "PRACTICAL_COMPONENT_RECORDED"
    STUDENT_CONFIRMATION = "STUDENT_CONFIRMATION"
    CERTIFICATE_ISSUED = "CERTIFICATE_ISSUED"
    STATE_TRANSITION = "STATE_TRANSITION"
    EVIDENCE_EXPORTED = "EVIDENCE_EXPORTED"


class EnrollmentComplianceProgress(Base):
    """Materialized current regulatory state for one enrollment.

    Source facts remain in lesson progress, assessments, practical records,
    signature evidence and certificates. This row is a query-friendly current
    state/cache; every transition is also appended to TrainingAccessEvent.
    """

    __tablename__ = "enrollment_compliance_progress"
    __table_args__ = (
        UniqueConstraint("tenant_id", "enrollment_id", name="uq_enrollment_compliance_progress"),
        Index("ix_enrollment_compliance_tenant_state", "tenant_id", "state"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    state = Column(String(64), nullable=False, default=RegulatoryCompletionState.ENROLLED, index=True)
    blockers = Column(JSONB, nullable=False, default=list)
    state_updated_at = Column(DateTime, default=utc_now, nullable=False)
    last_evaluated_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class PracticalTrainingRecord(Base):
    """Immutable practical-component observation.

    Corrections are represented by a newer record, optionally linked through
    ``supersedes_id``. Eligibility always uses the latest record, preserving
    the full evidence history instead of rewriting it.
    """

    __tablename__ = "practical_training_records"
    __table_args__ = (
        Index("ix_practical_training_enrollment_time", "tenant_id", "enrollment_id", "performed_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    instructor_id = Column(UUID(as_uuid=True), ForeignKey("training_professionals.id", ondelete="RESTRICT"), nullable=False, index=True)
    supersedes_id = Column(UUID(as_uuid=True), ForeignKey("practical_training_records.id", ondelete="RESTRICT"), nullable=True, index=True)
    result = Column(String(32), nullable=False, index=True)
    performed_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    location = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)
    instructor_snapshot = Column(JSONB, nullable=False)
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class TrainingAccessEvent(Base):
    """Append-only, privacy-minimized regulatory training ledger."""

    __tablename__ = "training_access_events"
    __table_args__ = (
        Index("ix_training_access_enrollment_time", "tenant_id", "enrollment_id", "occurred_at"),
        Index("ix_training_access_course_time", "tenant_id", "course_id", "occurred_at"),
        Index("ix_training_access_session", "tenant_id", "session_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False, index=True)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    occurred_at = Column(DateTime, default=utc_now, nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    client_fingerprint = Column(String(64), nullable=True)
    details = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now, nullable=False)
