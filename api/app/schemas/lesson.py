from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.lesson import LessonContentType


class LessonBase(BaseModel):
    course_id: UUID
    title: str
    description: str | None = None
    order: int = 0
    content_type: LessonContentType = LessonContentType.UPLOAD
    video_url: str | None = None
    storage_key: str | None = None
    duration_seconds: int | None = None
    is_free_preview: bool = False


class LessonCreate(LessonBase):
    pass


class LessonUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    order: int | None = None
    content_type: LessonContentType | None = None
    video_url: str | None = None
    storage_key: str | None = None
    duration_seconds: int | None = None
    is_free_preview: bool | None = None


class LessonResponse(LessonBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LessonMaterialBase(BaseModel):
    lesson_id: UUID
    title: str
    file_url: str


class LessonMaterialCreate(LessonMaterialBase):
    pass


class LessonMaterialResponse(LessonMaterialBase):
    id: UUID
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
