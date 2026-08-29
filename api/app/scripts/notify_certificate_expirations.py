"""Certificate expiration notification service.

Selects certificates nearing expiration and sends idempotent notifications.
This is a manually-executable / job-ready script — no external cron is
activated. Run via:

    python -m app.scripts.notify_certificate_expirations --days 30

The script is idempotent: re-running with the same --days window will not
send duplicate emails (dedup key includes the window).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.enrollment import Enrollment
from app.services.transactional_notifications import (
    send_certificate_expiration_notification,
)

logger = logging.getLogger(__name__)


async def notify_expiring_certificates(
    days: int = 30,
    *,
    dry_run: bool = False,
) -> dict:
    """Send expiration warnings for certificates expiring within `days` days.

    Returns a summary dict with counts.
    Idempotent: each certificate+window combination produces at most 1 email.
    """
    cutoff = utc_now() + timedelta(days=days)
    now = utc_now()

    async with AsyncSessionLocal() as db:
        # Find ACTIVE certificates expiring within the window
        # (not yet expired, but will expire soon)
        stmt = (
            select(Certificate, Enrollment)
            .join(Enrollment, Certificate.enrollment_id == Enrollment.id)
            .where(
                Certificate.status == "ACTIVE",
                Certificate.expires_at.is_not(None),
                Certificate.expires_at > now,
                Certificate.expires_at <= cutoff,
            )
        )
        rows = (await db.execute(stmt)).all()

        summary = {
            "scanned": len(rows),
            "notified": 0,
            "skipped": 0,
            "failed": 0,
            "dry_run": dry_run,
        }

        for cert, enrollment in rows:
            if dry_run:
                summary["skipped"] += 1
                continue

            try:
                result = await send_certificate_expiration_notification(
                    db,
                    enrollment_id=enrollment.id,
                    tenant_id=enrollment.tenant_id,
                    certificate_number=cert.certificate_number,
                    expires_at=cert.expires_at.isoformat() if cert.expires_at else "",
                    certificate_id=cert.id,
                    window=f"{days}d",
                )
                if result:
                    summary["notified"] += 1
                else:
                    summary["skipped"] += 1
                await db.commit()
            except Exception:
                logger.exception(
                    "Failed to send expiration notification for certificate %s",
                    cert.id,
                )
                summary["failed"] += 1
                await db.rollback()

    return summary


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send certificate expiration notifications"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days before expiration to send warnings (default: 30)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List certificates that would be notified without sending emails",
    )
    args = parser.parse_args(argv)

    summary = await notify_expiring_certificates(days=args.days, dry_run=args.dry_run)
    print(f"Certificate expiration notification summary: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
