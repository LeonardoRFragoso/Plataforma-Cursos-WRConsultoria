"""Lifecycle helpers for B2C payment attempts.

Only provider-less pending attempts are eligible for local expiration. Once an
external provider charge exists, provider reconciliation/webhooks remain the
source of truth so the platform never creates a second charge based solely on
an internal timeout.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.config import settings
from app.core.utils import utc_now
from app.models.payment import Payment, PaymentStatus


def _pending_attempt_ttl() -> timedelta:
    minutes = max(1, int(settings.PAYMENT_PENDING_ATTEMPT_TTL_MINUTES))
    return timedelta(minutes=minutes)


def has_external_charge(payment: Payment) -> bool:
    """Return whether this attempt has evidence of an external provider charge."""
    return bool(
        payment.provider_payment_id
        or payment.checkout_url
        or payment.mercado_pago_id
    )


def is_abandoned_pending_attempt(
    payment: Payment,
    *,
    now: datetime | None = None,
) -> bool:
    """Identify a stale internal attempt that is safe to expire locally."""
    if payment.status != PaymentStatus.PENDENTE:
        return False
    if has_external_charge(payment):
        return False
    if not payment.created_at:
        return False

    reference_time = now or utc_now()
    return payment.created_at <= reference_time - _pending_attempt_ttl()


def expire_abandoned_pending_attempt(
    payment: Payment,
    *,
    now: datetime | None = None,
) -> bool:
    """Mark a provider-less stale pending attempt as expired.

    Returns True only when this call changed the payment state.
    """
    if not is_abandoned_pending_attempt(payment, now=now):
        return False
    payment.status = PaymentStatus.EXPIRADO
    return True
