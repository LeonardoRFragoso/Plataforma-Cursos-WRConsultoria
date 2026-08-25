from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enrollment import EnrollmentSource, EnrollmentStatus
from app.models.payment import PaymentMethod
from app.schemas.payment import PaymentResponse


class EnrollmentBase(BaseModel):
    student_id: UUID
    class_id: UUID
    price: float
    status: EnrollmentStatus = EnrollmentStatus.PENDENTE
    source: EnrollmentSource = EnrollmentSource.INDIVIDUAL

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
    course_code: str | None = None
    course_category: str | None = None
    cover_image_url: str | None = None
    cover_image_alt: str | None = None
    class_id: UUID
    start_date: date
    end_date: date
    enrollment_date: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkEnrollmentCreate(BaseModel):
    class_id: UUID
    student_ids: list[UUID]
    price_per_student: float = 0.0
    company_id: UUID | None = None
    status: EnrollmentStatus = EnrollmentStatus.CONFIRMADA
    source: EnrollmentSource = EnrollmentSource.CORPORATE
    payment_method: PaymentMethod | None = None
    installments: str | None = None
    create_payment: bool = False


class BulkEnrollmentResponse(BaseModel):
    enrollment_ids: list[UUID]
    payment_id: UUID | None = None
    total_amount: float
    batch_id: UUID | None = None


class EnrollmentPurchaseRequest(BaseModel):
    course_id: UUID
    method: PaymentMethod = PaymentMethod.BOLETO


class EnrollmentPurchaseResponse(BaseModel):
    enrollment: EnrollmentResponse
    payment: PaymentResponse | None = None
