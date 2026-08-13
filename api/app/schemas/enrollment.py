from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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
    status: EnrollmentStatus | None = None
    price: float | None = None

class EnrollmentResponse(EnrollmentBase):
    id: UUID
    enrollment_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MyEnrollmentResponse(BaseModel):
    id: UUID
    status: EnrollmentStatus
    course_id: UUID
    course_name: str
    class_id: UUID
    start_date: date
    end_date: date
    enrollment_date: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkEnrollmentCreate(BaseModel):
    class_id: UUID
    student_ids: list[UUID]
    price_per_student: float
    company_id: UUID | None = None
    status: EnrollmentStatus = EnrollmentStatus.PENDENTE
    payment_method: PaymentMethod = PaymentMethod.BOLETO
    installments: str | None = None


class BulkEnrollmentResponse(BaseModel):
    enrollment_ids: list[UUID]
    payment_id: UUID
    total_amount: float
