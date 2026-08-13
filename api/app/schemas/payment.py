from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.models.payment import PaymentStatus, PaymentMethod

class PaymentBase(BaseModel):
    enrollment_id: UUID
    amount: float
    method: PaymentMethod
    installments: Optional[str] = None

class PaymentCreate(PaymentBase):
    pass

class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None

class PaymentResponse(PaymentBase):
    id: UUID
    status: PaymentStatus
    mercado_pago_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PaymentWebhookRequest(BaseModel):
    id: str
    status: str
    external_reference: Optional[str] = None
