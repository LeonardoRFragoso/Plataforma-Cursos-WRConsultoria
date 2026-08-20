"""Deterministic payment selection helper — single source of truth.

Used by the demo seed (`_get_or_create_payment`) and by the regression
tests in `api/tests/test_payment_selection.py`. The selection logic
MUST NOT be duplicated anywhere else — tests must execute this exact
production code path.

Selection order (deterministic, insertion-order independent):
1. APROVADO payments take priority over any other status
   (an approved payment is the most legitimate record).
2. Earliest `created_at` wins (oldest record is the most stable).
3. Stable UUID/id tie-breaker when priority and timestamp are equal.

This helper is read-only: it never creates, updates, or deletes
payment rows. Callers are responsible for creation when no payment
is found.
"""

from __future__ import annotations

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentStatus


def _selection_statement(enrollment_id):
    """Build the deterministic selection statement for an enrollment.

    Exposed as a function so tests can inspect the ordering without
    executing it, and so the ordering is defined in exactly one place.
    """
    return (
        select(Payment)
        .where(Payment.enrollment_id == enrollment_id)
        .order_by(
            case(
                (Payment.status == PaymentStatus.APROVADO, 0),
                else_=1,
            ),
            Payment.created_at,
            Payment.id,
        )
    )


async def select_payment_for_enrollment(
    db: AsyncSession,
    enrollment_id,
) -> Payment | None:
    """Return the deterministic best payment for an enrollment, or None.

    This is the production selector. It performs NO mutation and is
    safe to call from any read context (seed, reconciliation, tests).
    """
    result = await db.execute(_selection_statement(enrollment_id))
    payments = result.scalars().all()
    return payments[0] if payments else None


async def get_or_create_payment(
    db: AsyncSession,
    tenant_id,
    enrollment_id,
    amount: float,
):
    """Get-or-create a payment using the production selector.

    Returns a tuple `(payment, created)`:
    - `(existing_payment, False)` when at least one payment already exists
      for the enrollment — the deterministic selector picks the best one.
    - `(new_payment, True)` when no payment exists; a new APROVADO PIX
      payment is created and flushed.

    This is the ONLY creation path that uses the selector, ensuring the
    seed and any other caller share identical selection semantics.
    """
    from app.core.utils import utc_now
    from app.models.payment import PaymentMethod

    selected = await select_payment_for_enrollment(db, enrollment_id)
    if selected is not None:
        return selected, False

    payment = Payment(
        tenant_id=tenant_id,
        enrollment_id=enrollment_id,
        amount=amount,
        status=PaymentStatus.APROVADO,
        method=PaymentMethod.PIX,
        paid_at=utc_now(),
    )
    db.add(payment)
    await db.flush()
    return payment, True
