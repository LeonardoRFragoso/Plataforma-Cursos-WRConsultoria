"""Financial lifecycle rules that must not destroy learning history."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.utils import utc_now
from app.models.certificate import Certificate
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentStatus
from app.services.financial_review_service import ensure_payment_review

CHARGEBACK_REVIEW_EVENTS = frozenset({
    "PAYMENT_CHARGEBACK_REQUESTED",
    "PAYMENT_CHARGEBACK_DISPUTE",
    "PAYMENT_AWAITING_CHARGEBACK_REVERSAL",
    "MERCADO_PAGO_CHARGEBACK_IN_PROCESS",
})
REFUND_REVIEW_EVENTS = frozenset({"PAYMENT_PARTIALLY_REFUNDED", "PAYMENT_REFUND_IN_PROGRESS"})
REFUND_DENIED_EVENTS = frozenset({"PAYMENT_REFUND_DENIED"})
FULL_REFUND_EVENTS = frozenset({
    "PAYMENT_REFUNDED",
    "MERCADO_PAGO_REFUNDED",
    "MERCADO_PAGO_CHARGEBACK_SETTLED",
})
DISPUTE_WON_EVENTS = frozenset({"MERCADO_PAGO_CHARGEBACK_REIMBURSED"})
EXPIRY_EVENTS = frozenset({
    "PAYMENT_BANK_SLIP_CANCELLED",
    "MERCADO_PAGO_EXPIRED",
    "MERCADO_PAGO_CANCELLED",
})
SPECIAL_FINANCIAL_EVENTS = (
    CHARGEBACK_REVIEW_EVENTS
    | REFUND_REVIEW_EVENTS
    | REFUND_DENIED_EVENTS
    | FULL_REFUND_EVENTS
    | DISPUTE_WON_EVENTS
    | EXPIRY_EVENTS
)


def has_external_charge(payment: Payment) -> bool:
    return bool(payment.provider_payment_id or payment.checkout_url or payment.mercado_pago_id)


def expire_abandoned_internal_attempt(payment: Payment, *, now: datetime | None = None) -> bool:
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
    if event_type not in SPECIAL_FINANCIAL_EVENTS:
        raise ValueError(f"Unsupported special financial event: {event_type}")

    result = {
        "event": event_type,
        "payment_status": payment.status.value,
        "enrollment_status": enrollment.status.value if enrollment is not None else None,
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
            _mark_review(payment, f"unexpected_expiry_after_{payment.status.value.lower()}")

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
            protected_history = enrollment.status == EnrollmentStatus.CONCLUIDA or certificate_exists
            if protected_history:
                _mark_review(payment, "refund_after_completion_or_certificate")
            elif enrollment.status in (EnrollmentStatus.PENDENTE, EnrollmentStatus.CONFIRMADA):
                enrollment.status = EnrollmentStatus.CANCELADA
                result["access_revoked"] = True
                _clear_review(payment)
            else:
                _clear_review(payment)
        if already_refunded and not result["access_revoked"]:
            result["idempotent"] = True

    await ensure_payment_review(db, payment, source=event_type)
    result["payment_status"] = payment.status.value
    result["enrollment_status"] = enrollment.status.value if enrollment is not None else None
    result["review_required"] = bool(payment.review_required)
    result["review_reason"] = payment.review_reason
    return result
