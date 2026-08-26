"""CourseMaterial model — course-level materials (apostilas, manuals, etc.)
that are NOT tied to a specific lesson.

Unlike LessonMaterial, CourseMaterial does not affect lesson progress,
course completion, or certificate issuance. It is purely a downloadable
resource for enrolled students.

Access is tenant-scoped and requires course enrollment (or admin role).
"""
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import utc_now


class MaterialDocumentType:
    """Document type classification for course materials."""
    APOSTILA = "APOSTILA"
    MATERIAL_COMPLEMENTAR = "MATERIAL_COMPLEMENTAR"
    MANUAL = "MANUAL"
    REFERENCIA = "REFERENCIA"
    OUTRO = "OUTRO"


class CourseMaterial(Base):
    __tablename__ = "course_materials"

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
        index=True,
    )

    title = Column(String, nullable=False)
    storage_key = Column(String, nullable=False)  # private storage key
    mime_type = Column(String, nullable=False, default="application/pdf")
    size_bytes = Column(Integer, nullable=True)
    sha256 = Column(String, nullable=True, index=True)  # for dedup / provenance

    document_type = Column(
        String,
        default=MaterialDocumentType.APOSTILA,
        nullable=False,
    )

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    course = relationship("Course", backref="materials")

    def __repr__(self):
        return f"<CourseMaterial course_id={self.course_id} title={self.title}>"
