from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.course import CourseModality


class CourseBase(BaseModel):
    code: str
    name: str
    category: str
    description: str | None = None
    carga_horaria: int
    modality: CourseModality
    price: float
    prerequisites: str | None = None
    cover_image_url: str | None = None
    cover_image_alt: str | None = None
    is_active: bool = True

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    carga_horaria: int | None = None
    modality: CourseModality | None = None
    price: float | None = None
    prerequisites: str | None = None
    cover_image_url: str | None = None
    cover_image_alt: str | None = None
    is_active: bool | None = None

class CourseResponse(CourseBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
