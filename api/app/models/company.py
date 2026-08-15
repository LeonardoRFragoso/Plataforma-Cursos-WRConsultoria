import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class Company(Base):
    __tablename__ = "companies"

    __table_args__ = (
        UniqueConstraint("tenant_id", "cnpj", name="uq_company_tenant_cnpj"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        
        nullable=False,
        index=True,
    )
    legal_name = Column(String, nullable=False)
    trade_name = Column(String, nullable=True)
    cnpj = Column(String, index=True, nullable=False)
    rh_name = Column(String, nullable=True)
    rh_email = Column(String, nullable=True)
    rh_phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
