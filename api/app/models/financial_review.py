import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class FinancialReview(Base):
    __tablename__ = "financial_reviews"
    __table_args__ = (
        Index(
            "uq_financial_review_open_payment",
            "payment_id",
            unique=True,
            postgresql_where=text("status IN ('OPEN', 'IN_REVIEW')"),
            sqlite_where=text("status IN ('OPEN', 'IN_REVIEW')"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="OPEN", index=True)
    reason = Column(String, nullable=False)
    priority = Column(String, nullable=False, default="NORMAL", index=True)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    resolution_action = Column(String, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class FinancialReviewEvent(Base):
    __tablename__ = "financial_review_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    review_id = Column(UUID(as_uuid=True), ForeignKey("financial_reviews.id"), nullable=False, index=True)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
