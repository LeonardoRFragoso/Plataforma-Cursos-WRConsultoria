"""Notification event model for idempotent email delivery.

Each row represents a unique notification event (dedup key). When a
notification helper is called, it checks this table — if a row with
the same dedup_key already exists, the notification is not sent again.

This prevents duplicate emails from:
- Duplicate webhook deliveries
- Retry/reprocessing of the same event
- Race conditions in concurrent handlers
"""

import uuid

from sqlalchemy import Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.utils import utc_now


class NotificationEvent(Base):
    """Idempotency record for transactional notifications.

    dedup_key format examples:
    - payment-approved:{payment_id}
    - course-completed:{enrollment_id}
    - certificate-issued:{certificate_id}
    - certificate-expiration:{certificate_id}:{window}
    """

    __tablename__ = "notification_events"
    __table_args__ = (
        Index("ix_notification_events_tenant_type", "tenant_id", "notification_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # Unique dedup key — prevents duplicate notifications for the same event
    dedup_key = Column(String(256), nullable=False, unique=True, index=True)
    # Type of notification (e.g., "payment_approved", "course_completed")
    notification_type = Column(String(64), nullable=False, index=True)
    # Entity ID the notification is about (payment_id, enrollment_id, etc.)
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    # Delivery status: "PENDING", "SENT", "FAILED"
    status = Column(String(32), nullable=False, default="PENDING")
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)
