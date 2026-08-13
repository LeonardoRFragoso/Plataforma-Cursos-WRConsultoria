from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime, date
from app.models.class_model import ClassStatus

class ClassBase(BaseModel):
    course_id: UUID
    instructor_id: UUID
    start_date: date
    end_date: date
    max_students: int
    location: Optional[str] = None
    ead_link: Optional[str] = None
    description: Optional[str] = None
    status: ClassStatus = ClassStatus.ABERTA

class ClassCreate(ClassBase):
    pass

class ClassUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    max_students: Optional[int] = None
    location: Optional[str] = None
    ead_link: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ClassStatus] = None

class ClassResponse(ClassBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
