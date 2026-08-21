import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class CorporateEnrollmentBatch(Base):
    """Audit trail for bulk corporate enrollment operations.

    Records who provisioned which company's employees into which class,
    how many, and when. This is an operational traceability entity —
    not a CRM or contract management system.
    """
    __tablename__ = "corporate_enrollment_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("companies.id"),
        nullable=False,
        index=True,
    )
    class_id = Column(
        UUID(as_uuid=True),
        ForeignKey("classes.id"),
        nullable=False,
    )
    enrollment_count = Column(Integer, nullable=False)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_by_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
