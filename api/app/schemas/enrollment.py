from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.models.enrollment import EnrollmentStatus

class EnrollmentBase(BaseModel):
    student_id: UUID
    class_id: UUID
    price: float
    status: EnrollmentStatus = EnrollmentStatus.PENDENTE

class EnrollmentCreate(EnrollmentBase):
    pass

class EnrollmentUpdate(BaseModel):
    status: Optional[EnrollmentStatus] = None
    price: Optional[float] = None

class EnrollmentResponse(EnrollmentBase):
    id: UUID
    enrollment_date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
