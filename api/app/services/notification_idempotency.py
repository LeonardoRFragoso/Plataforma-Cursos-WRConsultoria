"""Idempotency service for transactional notifications.

Provides check_and_record() which atomically checks if a notification
has already been sent for a given dedup_key, and if not, records it.

Usage pattern in notification helpers:

    dedup_key = f"payment-approved:{payment_id}"
    if not await check_and_record(db, tenant_id, dedup_key, "payment_approved"):
        logger.info("Notification already sent for %s, skipping", dedup_key)
        return False
    # ... send email ...
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_event import NotificationEvent

logger = logging.getLogger(__name__)


async def check_and_record(
    db: AsyncSession,
    tenant_id: UUID,
    dedup_key: str,
    notification_type: str,
    entity_id: UUID | None = None,
) -> bool:
    """Atomically check if a notification was already sent, and record it.

    Returns True if this is the first call (notification should proceed).
    Returns False if a notification with this dedup_key already exists
    (notification should be skipped — idempotent).
    """
    # Check if already exists
    existing = await db.scalar(
        select(NotificationEvent).where(NotificationEvent.dedup_key == dedup_key)
    )
    if existing is not None:
        logger.info(
            "Notification already recorded for dedup_key=%s, skipping", dedup_key
        )
        return False

    # Record this notification attempt
    event = NotificationEvent(
        tenant_id=tenant_id,
        dedup_key=dedup_key,
        notification_type=notification_type,
        entity_id=entity_id,
        status="SENT",
    )
    db.add(event)
    try:
        await db.flush()
    except IntegrityError:
        # Concurrent insert — another handler beat us to it
        await db.rollback()
        logger.info(
            "Concurrent notification for dedup_key=%s, skipping", dedup_key
        )
        return False

    return True


def make_dedup_key(notification_type: str, entity_id: str | UUID) -> str:
    """Build a standard dedup key for a notification event."""
    return f"{notification_type}:{entity_id}"
