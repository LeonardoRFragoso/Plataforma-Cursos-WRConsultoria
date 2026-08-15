import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import utc_now


class LessonContentType(str, PyEnum):
    UPLOAD = "UPLOAD"
    YOUTUBE = "YOUTUBE"
    VIMEO = "VIMEO"


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        
        nullable=False,
        index=True,
    )
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    order = Column(Integer, default=0, nullable=False)
    content_type = Column(Enum(LessonContentType), default=LessonContentType.UPLOAD, nullable=False)
    video_url = Column(String, nullable=True)
    storage_key = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    is_free_preview = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    course = relationship("Course", backref="lessons")
    materials = relationship("LessonMaterial", backref="lesson", cascade="all, delete-orphan")
    progresses = relationship("LessonProgress", backref="lesson", cascade="all, delete-orphan")


class LessonMaterial(Base):
    __tablename__ = "lesson_materials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        
        nullable=False,
        index=True,
    )
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False)
    title = Column(String, nullable=False)
    file_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        
        nullable=False,
        index=True,
    )
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False)
    watched_seconds = Column(Integer, default=0, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_lesson_progress_student_lesson"),
    )
