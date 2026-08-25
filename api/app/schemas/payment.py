from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.payment import PaymentMethod, PaymentProvider, PaymentStatus


class PaymentBase(BaseModel):
    # Individual course payments have enrollment_id; consolidated corporate
    # payments intentionally use company_id at the model layer and therefore
    # expose enrollment_id=None in API responses.
    enrollment_id: UUID | None = None
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
    provider: PaymentProvider = PaymentProvider.MERCADO_PAGO
    provider_payment_id: str | None = None
    checkout_url: str | None = None
    mercado_pago_id: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Context used by the payment-return journey. These fields are populated
    # by GET /payments/{id} for individual course payments and remain null for
    # contexts where there is no single course/enrollment (e.g. company billing).
    course_id: UUID | None = None
    enrollment_status: str | None = None

    model_config = ConfigDict(from_attributes=True)

class PaymentWebhookRequest(BaseModel):
    id: str
    status: str
    external_reference: str | None = None


class AsaasWebhookEvent(BaseModel):
    """Payload de um webhook do Asaas.

    O Asaas envia ``{"id", "event", "payment": {"id": ...}}``. O campo
    ``payment`` pode conter o objeto completo ou apenas o id.
    """

    id: str
    event: str
    payment: dict | None = None
