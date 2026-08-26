"""Shared payment reconciliation service.

Both provider webhooks and the demo payment simulator call the same
reconciliation core to ensure identical state transitions.
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
    transitions. Provider webhooks and the demo simulator must call this.

    Rules:
    - Idempotent: if payment is already in the target status, no-op.
    - On APROVADO: sets paid_at, confirms enrollment ONLY if amounts match.
    - On RECUSADO/REEMBOLSADO/PROCESSANDO: sets payment status only.
    - Amount mismatch on APROVADO: payment is approved but enrollment
      is NOT confirmed.
    - ``enrollment_newly_confirmed`` is true only for the transition that
      actually unlocks the enrollment. It is safe to use as the trigger for
      one-time side effects such as the course-access notification email.

    Returns a dict describing what happened.
    """
    result = {
        "payment_status": new_status.value,
        "enrollment_status": (
            enrollment.status.value
            if hasattr(enrollment.status, "value")
            else str(enrollment.status)
        ),
        "amount_match": True,
        "enrollment_confirmed": False,
        "enrollment_newly_confirmed": False,
        "idempotent": payment.status == new_status,
    }

    # Idempotent: already in target status. Preserve the existing contract
    # (enrollment_confirmed reflects current access), but never claim a new
    # confirmation happened now.
    if payment.status == new_status:
        result["enrollment_confirmed"] = (
            enrollment.status == EnrollmentStatus.CONFIRMADA
        )
        return result

    payment.status = new_status

    if new_status == PaymentStatus.APROVADO:
        payment.paid_at = utc_now()
        amount_match = _amounts_match(payment.amount, enrollment.price)
        result["amount_match"] = amount_match
        if amount_match and enrollment.status != EnrollmentStatus.CONFIRMADA:
            enrollment.status = EnrollmentStatus.CONFIRMADA
            result["enrollment_confirmed"] = True
            result["enrollment_newly_confirmed"] = True
        elif amount_match:
            result["enrollment_confirmed"] = True
    elif new_status in (PaymentStatus.RECUSADO, PaymentStatus.REEMBOLSADO):
        # Access/revocation policy for an enrollment that was previously paid
        # is a separate business rule. Reconciliation does not silently revoke
        # access or destroy certificate history.
        pass

    result["enrollment_status"] = (
        enrollment.status.value
        if hasattr(enrollment.status, "value")
        else str(enrollment.status)
    )
    return result
