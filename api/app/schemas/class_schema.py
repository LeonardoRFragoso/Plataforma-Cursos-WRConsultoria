from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.class_model import ClassStatus


class ClassBase(BaseModel):
    course_id: UUID
    responsible_admin_id: UUID
    start_date: date
    end_date: date
    max_students: int
    location: str | None = None
    ead_link: str | None = None
    description: str | None = None
    status: ClassStatus = ClassStatus.ABERTA

class ClassCreate(ClassBase):
    pass

class ClassUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    max_students: int | None = None
    location: str | None = None
    ead_link: str | None = None
    description: str | None = None
    status: ClassStatus | None = None

class ClassResponse(ClassBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
