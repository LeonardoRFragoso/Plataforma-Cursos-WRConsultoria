import uuid
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class SubscriptionStatus(str, PyEnum):
    PENDENTE = "PENDENTE"
    ATIVO = "ATIVO"
    CANCELADO = "CANCELADO"
    EXPIRADO = "EXPIRADO"


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plans.id"),
        nullable=False,
        index=True,
    )
    status = Column(String, default=SubscriptionStatus.PENDENTE, nullable=False)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    mercado_pago_id = Column(String, nullable=True)
    external_reference = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
