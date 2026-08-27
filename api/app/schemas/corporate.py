from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.normalization import validate_cnpj


class CorporateRequestCreate(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    cnpj: str | None = None
    contact_name: str = Field(..., min_length=2, max_length=255)
    contact_email: EmailStr
    contact_phone: str | None = None
    course_interest: str | None = None
    employee_count: int | None = Field(default=None, ge=1, le=100000)
    message: str | None = None

    @field_validator("cnpj")
    @classmethod
    def validate_request_cnpj(cls, value: str | None) -> str | None:
        return validate_cnpj(value) if value else value


class CorporateRequestUpdate(BaseModel):
    status: str | None = None
    assigned_to: UUID | None = None
    admin_notes: str | None = None


class CorporateRequestResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    company_name: str
    cnpj: str | None = None
    contact_name: str
    contact_email: str
    contact_phone: str | None = None
    course_interest: str | None = None
    employee_count: int | None = None
    message: str | None = None
    status: str
    assigned_to: UUID | None = None
    admin_notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CorporateRequestConvert(BaseModel):
    trade_name: str | None = None
    billing_email: EmailStr | None = None
    contract_reference: str | None = None
    notes: str | None = None


class CorporateRequestConvertResponse(BaseModel):
    request_id: UUID
    company_id: UUID
    created: bool
    status: str


class CorporateInviteCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    cpf: str | None = None
    phone: str | None = None


class CorporateInviteResponse(BaseModel):
    id: UUID
    company_id: UUID
    student_id: UUID | None = None
    email: str
    full_name: str | None = None
    status: str
    expires_at: datetime | None = None
    created_at: datetime
    activation_token: str | None = None
    activation_email_sent: bool = False


class CorporateLinkEmployeeRequest(BaseModel):
    student_id: UUID | None = None
    email: EmailStr | None = None


class CorporateOffboardRequest(BaseModel):
    deactivate_account: bool = False
    cancel_active_corporate_enrollments: bool = True


class CorporateSeatAllocationCreate(BaseModel):
    class_id: UUID
    seats_reserved: int = Field(..., ge=1)
    expires_at: datetime | None = None
    notes: str | None = None


class CorporateSeatAllocationResponse(BaseModel):
    id: UUID
    company_id: UUID
    class_id: UUID
    seats_reserved: int
    seats_used: int
    seats_available: int
    is_active: bool
    expires_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class CorporateBulkEnrollRequest(BaseModel):
    class_id: UUID
    student_ids: list[UUID] = Field(..., min_length=1, max_length=1000)
    unit_price: float | None = Field(default=None, ge=0)


class CorporateBulkEnrollResponse(BaseModel):
    batch_id: UUID
    requested: int
    created: int
    existing: int
    rejected: int
    enrollment_ids: list[UUID]
    errors: list[str]


class CorporateEmployeeReportRow(BaseModel):
    student_id: UUID
    full_name: str
    email: str
    active: bool
    total_enrollments: int
    active_enrollments: int
    completed_enrollments: int
    certificates: int


class CorporateTrainingReport(BaseModel):
    company_id: UUID
    total_employees: int
    total_enrollments: int
    active_enrollments: int
    completed_enrollments: int
    certificates: int
    completion_rate: float
    employees: list[CorporateEmployeeReportRow]
