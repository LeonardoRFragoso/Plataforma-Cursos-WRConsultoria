from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import utc_now
from app.models.financial_review import FinancialReview, FinancialReviewEvent
from app.models.payment import Payment

_OPEN_STATUSES = ("OPEN", "IN_REVIEW")
_PRIORITY_RANK = {"LOW": 0, "NORMAL": 1, "HIGH": 2}


def priority_for_reason(reason: str | None) -> str:
    value = (reason or "").lower()
    if "chargeback" in value or "refund_after" in value:
        return "HIGH"
    if "refund" in value or "expiry_after" in value:
        return "NORMAL"
    return "LOW"


def _higher_priority(current: str | None, inferred: str) -> str:
    """Never downgrade an operator-selected priority during materialization."""
    normalized = (current or "LOW").upper()
    return inferred if _PRIORITY_RANK.get(inferred, 0) > _PRIORITY_RANK.get(normalized, 0) else normalized


async def ensure_payment_review(
    db: AsyncSession,
    payment: Payment,
    *,
    source: str | None = None,
) -> FinancialReview | None:
    """Keep Payment.review_required and the operator queue synchronized."""
    existing = (
        await db.execute(
            select(FinancialReview)
            .where(
                FinancialReview.tenant_id == payment.tenant_id,
                FinancialReview.payment_id == payment.id,
                FinancialReview.status.in_(_OPEN_STATUSES),
            )
            .order_by(FinancialReview.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if payment.review_required:
        reason = payment.review_reason or "manual_review_required"
        inferred_priority = priority_for_reason(reason)
        if existing:
            changed = existing.reason != reason
            existing.reason = reason
            existing.priority = _higher_priority(existing.priority, inferred_priority)
            if changed:
                db.add(
                    FinancialReviewEvent(
                        tenant_id=payment.tenant_id,
                        review_id=existing.id,
                        payment_id=payment.id,
                        event_type="REASON_UPDATED",
                        details=f"{source or 'payment'}:{reason}",
                    )
                )
            return existing

        review = FinancialReview(
            tenant_id=payment.tenant_id,
            payment_id=payment.id,
            status="OPEN",
            reason=reason,
            priority=inferred_priority,
        )
        db.add(review)
        await db.flush()
        db.add(
            FinancialReviewEvent(
                tenant_id=payment.tenant_id,
                review_id=review.id,
                payment_id=payment.id,
                event_type="OPENED",
                details=f"{source or 'payment'}:{reason}",
            )
        )
        return review

    if existing:
        existing.status = "DISMISSED"
        existing.resolution_action = "AUTO_CLEARED"
        existing.resolution_notes = "Payment review flag was cleared by financial lifecycle reconciliation."
        existing.resolved_at = utc_now()
        db.add(
            FinancialReviewEvent(
                tenant_id=payment.tenant_id,
                review_id=existing.id,
                payment_id=payment.id,
                event_type="AUTO_CLEARED",
                details=source,
            )
        )
    return existing


async def materialize_pending_reviews(db: AsyncSession, tenant_id) -> int:
    payments = (
        await db.execute(
            select(Payment).where(
                Payment.tenant_id == tenant_id,
                Payment.review_required.is_(True),
            )
        )
    ).scalars().all()
    count = 0
    for payment in payments:
        review = await ensure_payment_review(db, payment, source="queue_materialization")
        if review:
            count += 1
    await db.flush()
    return count
