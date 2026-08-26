from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentMethod, PaymentProvider, PaymentStatus


class FinancialReviewResponse(BaseModel):
    id: UUID
    payment_id: UUID
    status: str
    reason: str
    priority: str
    assigned_to: UUID | None = None
    resolution_action: str | None = None
    resolution_notes: str | None = None
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    payment_status: PaymentStatus
    payment_amount: float
    provider: PaymentProvider
    provider_payment_id: str | None = None
    enrollment_id: UUID | None = None
    company_id: UUID | None = None
    review_required: bool
    created_at: datetime
    updated_at: datetime


class FinancialReviewClaim(BaseModel):
    priority: str | None = None


class FinancialReviewResolution(BaseModel):
    action: str
    notes: str = Field(..., min_length=3, max_length=4000)


class ManualReviewCreate(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)
    priority: str = "NORMAL"


class CorporatePaymentCreate(BaseModel):
    company_id: UUID
    amount: float = Field(..., gt=0)
    method: PaymentMethod
    provider: PaymentProvider = PaymentProvider.ASAAS
    installments: str | None = None
    reference: str | None = None


class CorporatePaymentResponse(BaseModel):
    id: UUID
    company_id: UUID | None
    amount: float
    method: PaymentMethod
    provider: PaymentProvider
    status: PaymentStatus
    provider_payment_id: str | None = None
    checkout_url: str | None = None
    review_required: bool
    review_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FinancialSummaryResponse(BaseModel):
    approved_total: float
    refunded_total: float
    net_total: float
    monthly_approved: float
    monthly_refunded: float
    monthly_net: float
    open_reviews: int
    in_review: int
    pending_payments: int
    processing_payments: int
    approved_payments: int
    refunded_payments: int
    expired_payments: int
    corporate_payments: int


class FinancialReviewEventResponse(BaseModel):
    id: UUID
    review_id: UUID
    payment_id: UUID
    event_type: str
    actor_id: UUID | None = None
    details: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
