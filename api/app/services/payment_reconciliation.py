"""Shared payment reconciliation service.

Both the Mercado Pago webhook and the demo payment simulator call
the same reconciliation core to ensure identical state transitions.
"""

from app.core.utils import utc_now
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentStatus


def _amounts_match(a: float, b: float) -> bool:
    return abs(a - b) < 0.01


async def reconcile_payment_status(
    payment: Payment,
    enrollment: Enrollment,
    new_status: PaymentStatus,
) -> dict:
    """Apply a payment status transition and confirm enrollment if appropriate.

    This is the SINGLE source of truth for payment → enrollment state
    transitions. Both the webhook and the demo simulator must call this.

    Rules:
    - Idempotent: if payment is already in the target status, no-op.
    - On APROVADO: sets paid_at, confirms enrollment ONLY if amounts match.
    - On RECUSADO: sets payment status only.
    - On PROCESSANDO: sets payment status only.
    - Amount mismatch on APROVADO: payment is approved but enrollment
      is NOT confirmed.

    Returns a dict describing what happened:
    {
        "payment_status": str,
        "enrollment_status": str,
        "amount_match": bool,
        "enrollment_confirmed": bool,
        "idempotent": bool,
    }
    """
    result = {
        "payment_status": new_status.value,
        "enrollment_status": enrollment.status.value if hasattr(enrollment.status, "value") else str(enrollment.status),
        "amount_match": True,
        "enrollment_confirmed": False,
        "idempotent": payment.status == new_status,
    }

    # Idempotent: already in target status
    if payment.status == new_status:
        result["enrollment_confirmed"] = enrollment.status == EnrollmentStatus.CONFIRMADA
        return result

    payment.status = new_status

    if new_status == PaymentStatus.APROVADO:
        payment.paid_at = utc_now()
        amount_match = _amounts_match(payment.amount, enrollment.price)
        result["amount_match"] = amount_match
        if amount_match and enrollment.status != EnrollmentStatus.CONFIRMADA:
            enrollment.status = EnrollmentStatus.CONFIRMADA
            result["enrollment_confirmed"] = True
        elif amount_match:
            result["enrollment_confirmed"] = True
    elif new_status in (PaymentStatus.RECUSADO, PaymentStatus.REEMBOLSADO):
        # Do NOT unconfirm enrollment on rejection — the payment was
        # never approved, so enrollment stays in its prior state.
        pass

    result["enrollment_status"] = enrollment.status.value if hasattr(enrollment.status, "value") else str(enrollment.status)
    return result
