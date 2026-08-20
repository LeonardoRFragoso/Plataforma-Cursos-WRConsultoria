from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.lesson import LessonContentType


class LessonCreate(BaseModel):
    """Payload for creating a lesson.

    course_id is NOT accepted here — it comes from the route path
    POST /courses/{course_id}/lessons. storage_key is backend-owned
    state set only after upload verification.
    """
    title: str
    description: str | None = None
    order: int = 0
    content_type: LessonContentType = LessonContentType.UPLOAD
    video_url: str | None = None
    duration_seconds: int | None = None
    is_free_preview: bool = False
    is_required: bool = True


class LessonUpdate(BaseModel):
    """Payload for updating a lesson.

    storage_key is NOT writable here — it is backend-owned state
    managed exclusively by the upload-complete endpoint.
    """
    title: str | None = None
    description: str | None = None
    order: int | None = None
    content_type: LessonContentType | None = None
    video_url: str | None = None
    duration_seconds: int | None = None
    is_free_preview: bool | None = None
    is_required: bool | None = None


class LessonResponse(BaseModel):
    """Generic lesson response (admin/context-less)."""
    id: UUID
    tenant_id: UUID
    course_id: UUID
    title: str
    description: str | None = None
    order: int
    content_type: LessonContentType
    video_url: str | None = None
    storage_key: str | None = None
    duration_seconds: int | None = None
    is_free_preview: bool
    is_required: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonWithProgressResponse(BaseModel):
    """Lesson response with student-specific progress data.

    Used for authenticated student learning pages where per-student
    completion state must be shown alongside lesson metadata.
    """
    id: UUID
    tenant_id: UUID
    course_id: UUID
    title: str
    description: str | None = None
    order: int
    content_type: LessonContentType
    video_url: str | None = None
    storage_key: str | None = None
    duration_seconds: int | None = None
    is_free_preview: bool
    is_required: bool
    created_at: datetime
    updated_at: datetime
    # Student-specific progress (None if no progress record yet)
    watched_seconds: int = 0
    completed: bool = False
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class LessonReorderItem(BaseModel):
    id: UUID


class LessonReorderRequest(BaseModel):
    """Payload for reordering lessons in a course."""
    lesson_ids: list[UUID]


class LessonMaterialCreate(BaseModel):
    """Payload for creating a material record.

    storage_key is backend-owned. file_url is kept for backward
    compatibility with legacy material records.
    """
    title: str
    file_url: str | None = None


class LessonMaterialResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    lesson_id: UUID
    title: str
    file_url: str | None = None
    storage_key: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonProgressBase(BaseModel):
    watched_seconds: int = 0
    completed: bool = False


class LessonProgressCreate(LessonProgressBase):
    pass


class LessonProgressUpdate(BaseModel):
    watched_seconds: int | None = None
    completed: bool | None = None


class LessonProgressResponse(BaseModel):
    id: UUID
    student_id: UUID
    lesson_id: UUID
    watched_seconds: int
    completed: bool
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseProgressResponse(BaseModel):
    course_id: UUID
    total_lessons: int
    completed_lessons: int
    percentage: float


class CourseProgressDetailResponse(BaseModel):
    """Detailed course progress including required/optional breakdown."""
    course_id: UUID
    total_lessons: int
    required_lessons: int
    optional_lessons: int
    completed_required: int
    completed_optional: int
    percentage: float
    certificate_eligible: bool


class UploadPresignRequest(BaseModel):
    """Request for a presigned upload URL."""
    filename: str
    mime_type: str
    size_bytes: int


class UploadPresignResponse(BaseModel):
    """Response with presigned upload URL and storage key."""
    upload_url: str
    storage_key: str


class MaterialUploadPresignRequest(BaseModel):
    """Request for a presigned material upload URL."""
    filename: str
    mime_type: str
    size_bytes: int


class MaterialUploadPresignResponse(BaseModel):
    """Response with presigned material upload URL and storage key."""
    upload_url: str
    storage_key: str
