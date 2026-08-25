import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class PaymentStatus(str, PyEnum):
    PENDENTE = "PENDENTE"
    PROCESSANDO = "PROCESSANDO"
    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"
    REEMBOLSADO = "REEMBOLSADO"
    EXPIRADO = "EXPIRADO"


class PaymentMethod(str, PyEnum):
    CARTAO = "CARTAO"
    BOLETO = "BOLETO"
    PIX = "PIX"
    UNDEFINED = "UNDEFINED"


class PaymentProvider(str, PyEnum):
    MERCADO_PAGO = "MERCADO_PAGO"
    ASAAS = "ASAAS"


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index(
            "uq_payment_active_attempt_per_enrollment",
            "enrollment_id",
            unique=True,
            postgresql_where=text(
                "enrollment_id IS NOT NULL AND "
                "status IN ('PENDENTE', 'PROCESSANDO')"
            ),
            sqlite_where=text(
                "enrollment_id IS NOT NULL AND "
                "status IN ('PENDENTE', 'PROCESSANDO')"
            ),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDENTE, nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False)
    # Generic provider fields (MERCADO_PAGO, ASAAS).
    provider = Column(
        Enum(PaymentProvider),
        default=PaymentProvider.MERCADO_PAGO,
        nullable=False,
    )
    provider_payment_id = Column(String, nullable=True)
    checkout_url = Column(String, nullable=True)
    # Legacy Mercado Pago field. Kept for migration/lookup.
    mercado_pago_id = Column(String, nullable=True, unique=True)
    installments = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    # Financial events such as chargeback disputes, partial refunds or refunds
    # after course completion require human review instead of silently mutating
    # historical learning/certificate records.
    review_required = Column(Boolean, default=False, nullable=False)
    review_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class PaymentCustomer(Base):
    __tablename__ = "payment_customers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "provider",
            name="uq_payment_customer_student_provider",
        ),
        UniqueConstraint(
            "tenant_id",
            "company_id",
            "provider",
            name="uq_payment_customer_company_provider",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    provider = Column(
        Enum(PaymentProvider),
        default=PaymentProvider.MERCADO_PAGO,
        nullable=False,
    )
    provider_customer_id = Column(String, nullable=False)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "provider_event_id",
            name="uq_payment_webhook_event_provider",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    provider = Column(
        Enum(PaymentProvider),
        default=PaymentProvider.ASAAS,
        nullable=False,
    )
    provider_event_id = Column(String, nullable=False)
    event_type = Column(String, nullable=True)
    provider_payment_id = Column(String, nullable=True)
    payload = Column(String, nullable=True)
    processed_at = Column(DateTime, default=utc_now, nullable=False)
    result = Column(String, nullable=True)
