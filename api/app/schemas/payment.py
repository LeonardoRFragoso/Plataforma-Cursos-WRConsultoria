from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentMethod, PaymentStatus


class PaymentBase(BaseModel):
    enrollment_id: UUID
    amount: float
    method: PaymentMethod
    installments: str | None = None

class PaymentCreate(PaymentBase):
    pass

class PaymentUpdate(BaseModel):
    status: PaymentStatus | None = None

class PaymentResponse(PaymentBase):
    id: UUID
    status: PaymentStatus
    mercado_pago_id: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PaymentWebhookRequest(BaseModel):
    id: str
    status: str
    external_reference: str | None = None
