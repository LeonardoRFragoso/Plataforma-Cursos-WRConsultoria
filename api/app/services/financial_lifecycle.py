"""Financial lifecycle rules that must not destroy learning history.

Provider webhooks can report expiration, refund, partial refund and chargeback
states. These events are intentionally separated from ordinary approval/reject
reconciliation because access/certificate consequences are business rules.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentStatus

CHARGEBACK_REVIEW_EVENTS = frozenset(
    {
        "PAYMENT_CHARGEBACK_REQUESTED",
        "PAYMENT_CHARGEBACK_DISPUTE",
        "PAYMENT_AWAITING_CHARGEBACK_REVERSAL",
        "MERCADO_PAGO_CHARGEBACK_IN_PROCESS",
    }
)

REFUND_REVIEW_EVENTS = frozenset(
    {
        "PAYMENT_PARTIALLY_REFUNDED",
        "PAYMENT_REFUND_IN_PROGRESS",
    }
)

REFUND_DENIED_EVENTS = frozenset({"PAYMENT_REFUND_DENIED"})

FULL_REFUND_EVENTS = frozenset(
    {
        "PAYMENT_REFUNDED",
        "MERCADO_PAGO_REFUNDED",
        "MERCADO_PAGO_CHARGEBACK_SETTLED",
    }
)

DISPUTE_WON_EVENTS = frozenset(
    {
        "MERCADO_PAGO_CHARGEBACK_REIMBURSED",
    }
)

EXPIRY_EVENTS = frozenset(
    {
        "PAYMENT_BANK_SLIP_CANCELLED",
        "MERCADO_PAGO_EXPIRED",
        "MERCADO_PAGO_CANCELLED",
    }
)

SPECIAL_FINANCIAL_EVENTS = (
    CHARGEBACK_REVIEW_EVENTS
    | REFUND_REVIEW_EVENTS
    | REFUND_DENIED_EVENTS
    | FULL_REFUND_EVENTS
    | DISPUTE_WON_EVENTS
    | EXPIRY_EVENTS
)


def has_external_charge(payment: Payment) -> bool:
    """Whether an external provider charge has already been created."""
    return bool(
        payment.provider_payment_id
        or payment.checkout_url
        or payment.mercado_pago_id
    )


def expire_abandoned_internal_attempt(
    payment: Payment,
    *,
    now: datetime | None = None,
) -> bool:
    """Expire only stale PENDENTE attempts that never reached a provider.

    Once an external provider id/checkout exists, the provider remains the
    source of truth. This prevents a second charge from being created while an
    older boleto/PIX/card charge is still payable outside the platform.
    """
    if payment.status != PaymentStatus.PENDENTE:
        return False
    if has_external_charge(payment) or not payment.created_at:
        return False

    ttl_minutes = max(1, int(settings.PAYMENT_PENDING_ATTEMPT_TTL_MINUTES))
    cutoff = (now or utc_now()) - timedelta(minutes=ttl_minutes)
    if payment.created_at > cutoff:
        return False

    payment.status = PaymentStatus.EXPIRADO
    return True


async def _has_certificate(db: AsyncSession, enrollment: Enrollment) -> bool:
    stmt = select(Certificate.id).where(
        Certificate.enrollment_id == enrollment.id,
        Certificate.tenant_id == enrollment.tenant_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


def _mark_review(payment: Payment, reason: str) -> None:
    payment.review_required = True
    payment.review_reason = reason


def _clear_review(payment: Payment) -> None:
    payment.review_required = False
    payment.review_reason = None


async def reconcile_special_financial_event(
    db: AsyncSession,
    payment: Payment,
    enrollment: Enrollment | None,
    event_type: str,
) -> dict:
    """Apply expiration/refund/chargeback policy for provider events.

    Policy:
    - Expiration closes the payment attempt but leaves the enrollment pending so
      the student can start a new purchase attempt.
    - A chargeback request/dispute is *not* a final refund. Keep access/history
      unchanged and flag the payment for human review.
    - Full refund before completion/certificate cancels access automatically.
    - Full refund after completion or certificate issuance never destroys the
      learning/certificate record; it is flagged for manual review instead.
    - Partial/in-progress refunds require review because an automatic access
      decision would depend on commercial policy not encoded here.
    - A dispute resolved in the seller's favor clears the review flag and keeps
      the approved payment/access intact.
    """
    if event_type not in SPECIAL_FINANCIAL_EVENTS:
        raise ValueError(f"Unsupported special financial event: {event_type}")

    result = {
        "event": event_type,
        "payment_status": payment.status.value,
        "enrollment_status": (
            enrollment.status.value if enrollment is not None else None
        ),
        "access_revoked": False,
        "review_required": bool(payment.review_required),
        "review_reason": payment.review_reason,
        "idempotent": False,
    }

    if event_type in EXPIRY_EVENTS:
        if payment.status == PaymentStatus.EXPIRADO:
            result["idempotent"] = True
        elif payment.status in (PaymentStatus.PENDENTE, PaymentStatus.PROCESSANDO):
            payment.status = PaymentStatus.EXPIRADO
        else:
            # Never downgrade an approved/refunded payment because a stale
            # cancellation event arrived after a terminal financial event.
            _mark_review(payment, f"unexpected_expiry_after_{payment.status.value.lower()}")
        result["payment_status"] = payment.status.value

    elif event_type in CHARGEBACK_REVIEW_EVENTS:
        reason = f"chargeback_review:{event_type.lower()}"
        if payment.review_required and payment.review_reason == reason:
            result["idempotent"] = True
        _mark_review(payment, reason)

    elif event_type in REFUND_REVIEW_EVENTS:
        reason = f"refund_review:{event_type.lower()}"
        if payment.review_required and payment.review_reason == reason:
            result["idempotent"] = True
        _mark_review(payment, reason)

    elif event_type in REFUND_DENIED_EVENTS:
        if not payment.review_required:
            result["idempotent"] = True
        _clear_review(payment)

    elif event_type in DISPUTE_WON_EVENTS:
        # Mercado Pago documents charged_back/reimbursed as a resolution in
        # favor of the seller. Preserve the approved state and clear review.
        if not payment.review_required and payment.status == PaymentStatus.APROVADO:
            result["idempotent"] = True
        payment.status = PaymentStatus.APROVADO
        _clear_review(payment)

    elif event_type in FULL_REFUND_EVENTS:
        already_refunded = payment.status == PaymentStatus.REEMBOLSADO
        payment.status = PaymentStatus.REEMBOLSADO

        if enrollment is None:
            _mark_review(payment, "refund_without_individual_enrollment")
        else:
            certificate_exists = await _has_certificate(db, enrollment)
            protected_history = (
                enrollment.status == EnrollmentStatus.CONCLUIDA
                or certificate_exists
            )

            if protected_history:
                _mark_review(payment, "refund_after_completion_or_certificate")
            elif enrollment.status in (
                EnrollmentStatus.PENDENTE,
                EnrollmentStatus.CONFIRMADA,
            ):
                enrollment.status = EnrollmentStatus.CANCELADA
                result["access_revoked"] = True
                _clear_review(payment)
            else:
                # Already cancelled: the access consequence is already applied.
                _clear_review(payment)

        if already_refunded and not result["access_revoked"]:
            result["idempotent"] = True

    result["payment_status"] = payment.status.value
    result["enrollment_status"] = (
        enrollment.status.value if enrollment is not None else None
    )
    result["review_required"] = bool(payment.review_required)
    result["review_reason"] = payment.review_reason
    return result
