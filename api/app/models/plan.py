import uuid
from enum import Enum as PyEnum

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class BillingCycle(str, PyEnum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    ONE_TIME = "ONE_TIME"


class Plan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # tenant_id é NULL para planos do catálogo comercial global da WR.
    # Planos legados específicos de tenant mantêm o valor para compatibilidade.
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=True,
        index=True,
    )
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    billing_cycle = Column(String, default=BillingCycle.MONTHLY, nullable=False)
    features = Column(JSON, default=dict, nullable=False)
    max_users = Column(Integer, nullable=True)
    max_courses = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
