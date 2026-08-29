"""Idempotency service for transactional notifications.

State machine: PENDING → SENT | FAILED

This service uses its OWN database session (AsyncSessionLocal) to persist
idempotency records. It NEVER touches the caller's session — no flush,
no rollback, no commit on the passed-in AsyncSession.

Flow:
    1. reserve(dedup_key) → atomically INSERT PENDING (ON CONFLICT DO NOTHING)
       → returns True if this worker won the reservation
       → returns False if another worker already owns the key (SENT or PENDING)
    2. Caller sends the email
    3. mark_sent(dedup_key) → UPDATE status='SENT' (only if result is True)
       OR
       mark_failed(dedup_key) → UPDATE status='FAILED' (if result is False or exception)

Retry policy:
    - SENT → never send again (reserve returns False)
    - FAILED → can be retried atomically (UPDATE...WHERE status='FAILED' RETURNING id)
    - PENDING (stale, older than NOTIFICATION_PENDING_LEASE_SECONDS) → can be
      re-acquired atomically by exactly one worker
    - PENDING (recent) → skip (another worker owns it)

Concurrency:
    - New key: INSERT ON CONFLICT DO NOTHING — only one worker wins
    - FAILED retry: UPDATE...WHERE status='FAILED' RETURNING id — only one wins
    - Stale PENDING: UPDATE...WHERE status='PENDING' AND updated_at < cutoff RETURNING id
"""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.notification_event import NotificationEvent

logger = logging.getLogger(__name__)

STATUS_PENDING = "PENDING"
STATUS_SENT = "SENT"
STATUS_FAILED = "FAILED"


async def reserve(
    tenant_id: UUID,
    dedup_key: str,
    notification_type: str,
    entity_id: UUID | None = None,
) -> bool:
    """Atomically reserve a dedup key for this notification.

    Three paths, all atomic:
    1. New key: INSERT ON CONFLICT DO NOTHING → PENDING. Only one worker wins.
    2. Existing FAILED: UPDATE...WHERE status='FAILED' RETURNING id → PENDING.
       Only one worker wins the retry.
    3. Existing PENDING (stale): UPDATE...WHERE status='PENDING' AND
       updated_at < cutoff RETURNING id → PENDING. Only one worker wins recovery.

    Uses a dedicated session — does NOT touch the caller's session.

    Returns True if this worker should proceed to send the email.
    Returns False if the notification should be skipped.
    """
    now = utc_now()
    lease_cutoff = now - timedelta(seconds=settings.NOTIFICATION_PENDING_LEASE_SECONDS)

    async with AsyncSessionLocal() as db:
        # Path 1: Atomic insert with ON CONFLICT DO NOTHING
        stmt = (
            pg_insert(NotificationEvent)
            .values(
                tenant_id=tenant_id,
                dedup_key=dedup_key,
                notification_type=notification_type,
                entity_id=entity_id,
                status=STATUS_PENDING,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["dedup_key"])
            .returning(NotificationEvent.id)
        )
        result = await db.execute(stmt)
        row_id = result.scalar_one_or_none()

        if row_id is not None:
            await db.commit()
            logger.info("Reserved dedup_key=%s (new PENDING)", dedup_key)
            return True

        # Row already exists — try atomic FAILED retry
        retry_result = await db.execute(
            text(
                "UPDATE notification_events SET status = 'PENDING', updated_at = :now "
                "WHERE dedup_key = :key AND status = 'FAILED' "
                "RETURNING id"
            ),
            {"key": dedup_key, "now": now},
        )
        if retry_result.scalar_one_or_none() is not None:
            await db.commit()
            logger.info("Re-reserved dedup_key=%s (FAILED → PENDING retry)", dedup_key)
            return True

        # Try atomic stale PENDING recovery
        stale_result = await db.execute(
            text(
                "UPDATE notification_events SET status = 'PENDING', updated_at = :now "
                "WHERE dedup_key = :key AND status = 'PENDING' AND updated_at < :cutoff "
                "RETURNING id"
            ),
            {"key": dedup_key, "now": now, "cutoff": lease_cutoff},
        )
        if stale_result.scalar_one_or_none() is not None:
            await db.commit()
            logger.info("Re-reserved dedup_key=%s (stale PENDING recovery)", dedup_key)
            return True

        # SENT, or PENDING (recent) — skip
        await db.rollback()
        logger.info("dedup_key=%s already SENT or PENDING (recent), skipping", dedup_key)
        return False


async def mark_sent(dedup_key: str) -> None:
    """Mark a notification as successfully sent.

    Uses a dedicated session — does NOT touch the caller's session.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "UPDATE notification_events SET status = 'SENT', updated_at = :now "
                "WHERE dedup_key = :key"
            ),
            {"key": dedup_key, "now": utc_now()},
        )
        await db.commit()
        logger.info("Marked dedup_key=%s as SENT", dedup_key)


async def mark_failed(dedup_key: str) -> None:
    """Mark a notification as failed (can be retried later).

    Uses a dedicated session — does NOT touch the caller's session.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "UPDATE notification_events SET status = 'FAILED', updated_at = :now "
                "WHERE dedup_key = :key"
            ),
            {"key": dedup_key, "now": utc_now()},
        )
        await db.commit()
        logger.info("Marked dedup_key=%s as FAILED", dedup_key)


def make_dedup_key(notification_type: str, entity_id: str | UUID) -> str:
    """Build a standard dedup key for a notification event."""
    return f"{notification_type}:{entity_id}"
