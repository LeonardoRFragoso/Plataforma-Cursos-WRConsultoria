from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.models.course import CourseModality

class CourseBase(BaseModel):
    code: str
    name: str
    category: str
    description: Optional[str] = None
    carga_horaria: int
    modality: CourseModality
    price: float
    prerequisites: Optional[str] = None
    is_active: bool = True

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    carga_horaria: Optional[int] = None
    modality: Optional[CourseModality] = None
    price: Optional[float] = None
    prerequisites: Optional[str] = None
    is_active: Optional[bool] = None

class CourseResponse(CourseBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
