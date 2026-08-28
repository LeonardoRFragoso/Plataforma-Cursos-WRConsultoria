"""CourseContentProfile model — structured academic content extracted from
apostilas/source documents, kept separate from the commercial Course record.

This entity stores provenance-tracked, structured information (objectives,
target audience, syllabus, key topics, standards referenced, etc.) that can
be displayed on course detail pages and managed by admins without bloating
the Course.description field.

All JSON fields use PostgreSQL JSONB for efficient querying.
"""
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import utc_now


class ReviewStatus:
    """Review status for content profiles (not an enum to allow flexibility)."""
    SOURCE_CONFIRMED = "SOURCE_CONFIRMED"
    INFERRED = "INFERRED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CourseContentProfile(Base):
    __tablename__ = "course_content_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    course_id = Column(
        UUID(as_uuid=True),
        ForeignKey("courses.id"),
        nullable=False,
        unique=True,  # one profile per course
        index=True,
    )

    # Short text fields
    short_description = Column(Text, nullable=True)
    full_description = Column(Text, nullable=True)
    target_audience = Column(Text, nullable=True)
    general_objective = Column(Text, nullable=True)
    prerequisites = Column(Text, nullable=True)
    assessment_summary = Column(Text, nullable=True)
    recycling_summary = Column(Text, nullable=True)
    validity_summary = Column(Text, nullable=True)
    technical_responsible = Column(Text, nullable=True)

    # JSONB structured fields
    specific_objectives = Column(JSONB, nullable=True, default=list)
    learning_outcomes = Column(JSONB, nullable=True, default=list)
    syllabus = Column(JSONB, nullable=True, default=list)
    modules = Column(JSONB, nullable=True, default=list)
    key_topics = Column(JSONB, nullable=True, default=list)
    risks_covered = Column(JSONB, nullable=True, default=list)
    prevention_topics = Column(JSONB, nullable=True, default=list)
    ppe_topics = Column(JSONB, nullable=True, default=list)
    emergency_topics = Column(JSONB, nullable=True, default=list)
    standards_referenced = Column(JSONB, nullable=True, default=list)
    instructor_information = Column(JSONB, nullable=True, default=list)

    # Provenance and review tracking
    source_manifest = Column(JSONB, nullable=True)  # references to source PDFs, SHAs, pages
    review_status = Column(
        String,
        default=ReviewStatus.SOURCE_CONFIRMED,
        nullable=False,
    )
    review_required_fields = Column(JSONB, nullable=True, default=list)

    # Content approval audit trail — tracks when academic content
    # (syllabus, key_topics, risks, prevention) was confirmed against
    # the source apostila by the owner. Does NOT approve workload,
    # modality, practice, recycling, or technical responsible — those
    # have their own regulatory compliance cycle.
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    manifest_version = Column(String(128), nullable=True)  # manifest file version identifier
    manifest_hash = Column(String(64), nullable=True)  # SHA-256 of the source manifest file

    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    course = relationship("Course", backref="content_profile")

    def __repr__(self):
        return f"<CourseContentProfile course_id={self.course_id}>"
