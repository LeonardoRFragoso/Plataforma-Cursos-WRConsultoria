import uuid
from enum import Enum as PyEnum

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.utils import utc_now


class TenantStatus(str, PyEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"


class PartnerLeadStatus(str, PyEnum):
    NEW = "NEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CustomDomainStatus(str, PyEnum):
    NONE = "NONE"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    legal_name = Column(String, nullable=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    cnpj = Column(String, nullable=True)
    custom_domain = Column(String, unique=True, index=True, nullable=True)
    custom_domain_status = Column(
        String,
        default=CustomDomainStatus.NONE,
        nullable=False,
    )
    domain_verification_token = Column(String, nullable=True)
    domain_verified_at = Column(DateTime, nullable=True)
    domain_verification_error = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    logo_white_url = Column(String, nullable=True)
    favicon_url = Column(String, nullable=True)
    primary_color = Column(String, nullable=True)
    secondary_color = Column(String, nullable=True)
    accent_color = Column(String, nullable=True)
    status = Column(
        Enum(TenantStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        default=TenantStatus.ACTIVE,
        nullable=False,
    )
    plan = Column(String, nullable=True)
    contact_name = Column(String, nullable=False)
    contact_email = Column(String, nullable=False)
    contact_phone = Column(String, nullable=True)
    settings = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    partner_leads = relationship("PartnerLead", back_populates="tenant")


class PartnerLead(Base):
    __tablename__ = "partner_leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_name = Column(String, nullable=False)
    cnpj = Column(String, nullable=True)
    contact_name = Column(String, nullable=False)
    contact_email = Column(String, nullable=False)
    contact_phone = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    status = Column(
        Enum(PartnerLeadStatus, values_callable=lambda x: [e.value for e in x], native_enum=False),
        default=PartnerLeadStatus.NEW,
        nullable=False,
    )
    notes = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    tenant = relationship("Tenant", back_populates="partner_leads")
