import uuid
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class PaymentStatus(str, PyEnum):
    PENDENTE = "PENDENTE"
    PROCESSANDO = "PROCESSANDO"
    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"
    REEMBOLSADO = "REEMBOLSADO"

class PaymentMethod(str, PyEnum):
    CARTAO = "CARTAO"
    BOLETO = "BOLETO"
    PIX = "PIX"

class Payment(Base):
    __tablename__ = "payments"

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
    mercado_pago_id = Column(String, nullable=True, unique=True)
    installments = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
