from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.enrollment import EnrollmentStatus
from app.models.payment import PaymentMethod

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


class BulkEnrollmentCreate(BaseModel):
    class_id: UUID
    student_ids: List[UUID]
    price_per_student: float
    company_id: Optional[UUID] = None
    status: EnrollmentStatus = EnrollmentStatus.PENDENTE
    payment_method: PaymentMethod = PaymentMethod.BOLETO
    installments: Optional[str] = None


class BulkEnrollmentResponse(BaseModel):
    enrollment_ids: List[UUID]
    payment_id: UUID
    total_amount: float
