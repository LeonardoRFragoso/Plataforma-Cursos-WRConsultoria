from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Float
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
import uuid
from enum import Enum as PyEnum

from app.core.database import Base

class PaymentStatus(str, PyEnum):
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    APROVADO = "aprovado"
    RECUSADO = "recusado"
    REEMBOLSADO = "reembolsado"

class PaymentMethod(str, PyEnum):
    CARTAO = "cartao"
    BOLETO = "boleto"
    PIX = "pix"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollments.id"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDENTE, nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False)
    mercado_pago_id = Column(String, nullable=True, unique=True)
    installments = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
