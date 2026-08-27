import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class CorporateTrainingRequest(Base):
    """Public B2B training request captured for the current tenant."""

    __tablename__ = "corporate_training_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    company_name = Column(String, nullable=False)
    cnpj = Column(String, nullable=True, index=True)
    contact_name = Column(String, nullable=False)
    contact_email = Column(String, nullable=False, index=True)
    contact_phone = Column(String, nullable=True)
    course_interest = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    message = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="NEW", index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    admin_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CorporateInvite(Base):
    """Audit trail for corporate employee invitation/activation operations."""

    __tablename__ = "corporate_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=True, index=True)
    email = Column(String, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="PENDING", index=True)
    token_id = Column(UUID(as_uuid=True), ForeignKey("one_time_tokens.id"), nullable=True)
    invited_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CorporateSeatAllocation(Base):
    """Commercial/operational seat reservation for a company in a class."""

    __tablename__ = "corporate_seat_allocations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "company_id",
            "class_id",
            name="uq_corporate_seat_tenant_company_class",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id"), nullable=False, index=True)
    seats_reserved = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class CorporateEmployeeLinkEvent(Base):
    """Immutable audit record for company ↔ student membership changes."""

    __tablename__ = "corporate_employee_link_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False, index=True)
    previous_company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)
