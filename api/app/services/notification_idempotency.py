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
    3. mark_sent(dedup_key) → UPDATE status='SENT' in isolated session
       OR
       mark_failed(dedup_key) → UPDATE status='FAILED' in isolated session

Retry policy:
    - SENT → never send again (reserve returns False)
    - FAILED → can be retried (reserve resets to PENDING)
    - PENDING (stale) → treated as owned by another worker (reserve returns False)

Concurrency:
    - Unique constraint on dedup_key + INSERT ON CONFLICT DO NOTHING
    - Two simultaneous workers with same key → only one wins
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import AsyncSessionLocal
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

    Uses INSERT ... ON CONFLICT DO NOTHING against the unique dedup_key
    constraint. If the row already exists with status SENT or PENDING,
    returns False (another worker owns it or it was already sent).

    If the row exists with status FAILED, resets it to PENDING and
    returns True (retry allowed).

    Uses a dedicated session — does NOT touch the caller's session.

    Returns True if this worker should proceed to send the email.
    Returns False if the notification should be skipped.
    """
    async with AsyncSessionLocal() as db:
        # Atomic insert with ON CONFLICT DO NOTHING
        stmt = (
            pg_insert(NotificationEvent)
            .values(
                tenant_id=tenant_id,
                dedup_key=dedup_key,
                notification_type=notification_type,
                entity_id=entity_id,
                status=STATUS_PENDING,
            )
            .on_conflict_do_nothing(index_elements=["dedup_key"])
            .returning(NotificationEvent.id)
        )
        result = await db.execute(stmt)
        row_id = result.scalar_one_or_none()

        if row_id is not None:
            # We successfully inserted a new PENDING row
            await db.commit()
            logger.info("Reserved dedup_key=%s (new PENDING)", dedup_key)
            return True

        # Row already exists — check its status
        existing = await db.scalar(
            select(NotificationEvent).where(
                NotificationEvent.dedup_key == dedup_key
            )
        )
        if existing is None:
            # Should not happen, but handle gracefully
            logger.warning("Could not find existing row for dedup_key=%s", dedup_key)
            return False

        if existing.status == STATUS_FAILED:
            # Retry: reset to PENDING
            existing.status = STATUS_PENDING
            await db.commit()
            logger.info("Re-reserved dedup_key=%s (FAILED → PENDING retry)", dedup_key)
            return True

        # SENT or PENDING — skip
        logger.info(
            "dedup_key=%s already %s, skipping", dedup_key, existing.status
        )
        return False


async def mark_sent(dedup_key: str) -> None:
    """Mark a notification as successfully sent.

    Uses a dedicated session — does NOT touch the caller's session.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "UPDATE notification_events SET status = 'SENT' "
                "WHERE dedup_key = :key"
            ),
            {"key": dedup_key},
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
                "UPDATE notification_events SET status = 'FAILED' "
                "WHERE dedup_key = :key"
            ),
            {"key": dedup_key},
        )
        await db.commit()
        logger.info("Marked dedup_key=%s as FAILED", dedup_key)


def make_dedup_key(notification_type: str, entity_id: str | UUID) -> str:
    """Build a standard dedup key for a notification event."""
    return f"{notification_type}:{entity_id}"
