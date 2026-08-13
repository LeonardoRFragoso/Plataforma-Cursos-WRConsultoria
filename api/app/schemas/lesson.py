from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.lesson import LessonContentType


class LessonBase(BaseModel):
    course_id: UUID
    title: str
    description: Optional[str] = None
    order: int = 0
    content_type: LessonContentType = LessonContentType.UPLOAD
    video_url: Optional[str] = None
    storage_key: Optional[str] = None
    duration_seconds: Optional[int] = None
    is_free_preview: bool = False


class LessonCreate(LessonBase):
    pass


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    order: Optional[int] = None
    content_type: Optional[LessonContentType] = None
    video_url: Optional[str] = None
    storage_key: Optional[str] = None
    duration_seconds: Optional[int] = None
    is_free_preview: Optional[bool] = None


class LessonResponse(LessonBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LessonMaterialBase(BaseModel):
    lesson_id: UUID
    title: str
    file_url: str


class LessonMaterialCreate(LessonMaterialBase):
    pass


class LessonMaterialResponse(LessonMaterialBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class LessonProgressBase(BaseModel):
    lesson_id: UUID
    watched_seconds: int = 0
    completed: bool = False


class LessonProgressCreate(LessonProgressBase):
    pass


class LessonProgressUpdate(BaseModel):
    watched_seconds: Optional[int] = None
    completed: Optional[bool] = None


class LessonProgressResponse(BaseModel):
    id: UUID
    student_id: UUID
    lesson_id: UUID
    watched_seconds: int
    completed: bool
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CourseProgressResponse(BaseModel):
    course_id: UUID
    total_lessons: int
    completed_lessons: int
    percentage: float
