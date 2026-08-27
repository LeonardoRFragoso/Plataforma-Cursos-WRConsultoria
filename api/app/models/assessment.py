import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base
from app.core.utils import utc_now


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    question_version = Column(String, nullable=False, default="v1")
    answers = Column(JSONB, nullable=True)
    correct_answers = Column(Integer, nullable=True)
    total_questions = Column(Integer, nullable=False)
    minimum_score = Column(Float, nullable=False, default=60.0)
    score = Column(Float, nullable=True)
    passed = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("enrollment_id", "attempt_number", name="uq_assessment_enrollment_attempt"),
    )


class StudentSignatureEvidence(Base):
    __tablename__ = "student_signature_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False, unique=True, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False, index=True)
    assessment_attempt_id = Column(UUID(as_uuid=True), ForeignKey("assessment_attempts.id"), nullable=False)
    declaration_version = Column(String, nullable=False, default="nr1-demo-v1")
    auth_method = Column(String, nullable=False, default="PASSWORD_REAUTH")
    declaration_text_hash = Column(String, nullable=True)
    evidence_payload_hash = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    accepted_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
