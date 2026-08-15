from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentMethod, PaymentStatus


class PaymentBase(BaseModel):
    enrollment_id: UUID
    amount: float
    method: PaymentMethod
    installments: str | None = None

class PaymentCreate(BaseModel):
    """Schema público de criação de pagamento.

    O valor (amount) NUNCA é informado pelo cliente. É calculado server-side
    a partir da fonte confiável (Enrollment.price / Course.price) para evitar
    que um aluno pague menos que o preço real do curso.
    """

    enrollment_id: UUID
    method: PaymentMethod
    installments: str | None = None


class PaymentAdminCreate(BaseModel):
    """Criação administrativa explícita e auditável de pagamento.

    Reservada para ajustes manuais controlados (ex.: pagamento consolidado
    em lote). Não exposta no fluxo público de checkout de curso.
    """

    enrollment_id: UUID
    amount: float
    method: PaymentMethod
    installments: str | None = None


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
