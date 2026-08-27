"""Periodic payment reconciliation independent from provider webhooks.

The routine is intentionally read-only at the provider: it queries canonical
payment state and reconciles internal state. It never creates charges or
initiates refunds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import utc_now
from app.models.enrollment import Enrollment, EnrollmentStatus
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.tenant import Tenant
from app.services.asaas_provider import AsaasProvider
from app.services.financial_lifecycle import reconcile_special_financial_event
from app.services.financial_review_service import ensure_payment_review
from app.services.mercado_pago_provider import MercadoPagoProvider
from app.services.payment_provider_base import PaymentProviderError
from app.services.payment_reconciliation import reconcile_payment_status
from app.services.tenant_secret_service import (
    get_asaas_api_key,
    get_mercado_pago_access_token,
)
from app.services.transactional_notifications import send_course_access_notification

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderAction:
    kind: str  # normal | special | ignore
    value: PaymentStatus | str | None = None


def provider_status_action(
    provider: PaymentProvider,
    status_value: str,
    status_detail: str | None = None,
) -> ProviderAction:
    """Map canonical provider polling status to the existing lifecycle rules."""
    raw = (status_value or "").strip().upper()
    detail = (status_detail or "").strip().lower()

    if provider == PaymentProvider.ASAAS:
        if raw in {
            "PENDING",
            "AWAITING_RISK_ANALYSIS",
            "OVERDUE",
            "DUNNING_REQUESTED",
        }:
            return ProviderAction("normal", PaymentStatus.PROCESSANDO)
        if raw in {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH", "DUNNING_RECEIVED"}:
            return ProviderAction("normal", PaymentStatus.APROVADO)
        if raw == "REFUNDED":
            return ProviderAction("special", "PAYMENT_REFUNDED")
        if raw == "REFUND_IN_PROGRESS":
            return ProviderAction("special", "PAYMENT_REFUND_IN_PROGRESS")
        if raw == "REFUND_REQUESTED":
            return ProviderAction("normal", PaymentStatus.PROCESSANDO)
        if raw in {"CHARGEBACK_REQUESTED", "CHARGEBACK_DISPUTE", "AWAITING_CHARGEBACK_REVERSAL"}:
            return ProviderAction("special", f"PAYMENT_{raw}")
        if raw in {"DELETED", "CREDIT_CARD_CAPTURE_REFUSED"}:
            return ProviderAction("normal", PaymentStatus.RECUSADO)
        return ProviderAction("ignore", raw or "UNKNOWN")

    # Mercado Pago canonical payment status/status_detail values.
    if raw in {"PENDING", "IN_PROCESS", "IN_MEDIATION", "AUTHORIZED"}:
        return ProviderAction("normal", PaymentStatus.PROCESSANDO)
    if raw == "APPROVED":
        return ProviderAction("normal", PaymentStatus.APROVADO)
    if raw == "REJECTED":
        return ProviderAction("normal", PaymentStatus.RECUSADO)
    if raw in {"CANCELLED", "CANCELED"}:
        return ProviderAction("special", "MERCADO_PAGO_CANCELLED")
    if raw == "REFUNDED":
        return ProviderAction("special", "MERCADO_PAGO_REFUNDED")
    if raw == "CHARGED_BACK":
        if detail in {"reimbursed", "reimbursed_to_merchant"}:
            return ProviderAction("special", "MERCADO_PAGO_CHARGEBACK_REIMBURSED")
        if detail in {"settled", "lost"}:
            return ProviderAction("special", "MERCADO_PAGO_CHARGEBACK_SETTLED")
        return ProviderAction("special", "MERCADO_PAGO_CHARGEBACK_IN_PROCESS")
    return ProviderAction("ignore", raw or "UNKNOWN")


async def _provider_for_payment(
    db: AsyncSession,
    tenant: Tenant,
    provider_name: PaymentProvider,
):
    settings = dict(tenant.settings or {})
    if provider_name == PaymentProvider.ASAAS:
        api_key = await get_asaas_api_key(db, tenant.id)
        if not api_key:
            raise PaymentProviderError(
                "Asaas credentials are not configured",
                provider_error_code="missing_api_key",
            )
        return AsaasProvider(api_key=api_key, sandbox=bool(settings.get("asaas_sandbox", False)))

    token = await get_mercado_pago_access_token(db, tenant.id)
    token = token or settings.get("mp_access_token")
    if not token:
        raise PaymentProviderError(
            "Mercado Pago credentials are not configured",
            provider_error_code="missing_access_token",
        )
    return MercadoPagoProvider(access_token=token)


def _provider_lookup_id(payment: Payment) -> str | None:
    if payment.provider == PaymentProvider.MERCADO_PAGO:
        return payment.mercado_pago_id or payment.provider_payment_id
    return payment.provider_payment_id


async def reconcile_tenant_payments(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 250,
) -> dict:
    """Poll canonical provider state for financially relevant payments.

    Rows never reconciled are processed first, then the least-recently polled.
    Each payment uses a database savepoint so one malformed historical record
    cannot roll back successful reconciliation of the rest of the batch.
    """
    if limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")

    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise ValueError("Tenant not found")

    payments = (
        await db.execute(
            select(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.status.in_(
                    [PaymentStatus.PENDENTE, PaymentStatus.PROCESSANDO, PaymentStatus.APROVADO]
                ),
                or_(
                    Payment.provider_payment_id.is_not(None),
                    Payment.mercado_pago_id.is_not(None),
                ),
            )
            .order_by(
                Payment.last_reconciled_at.asc().nullsfirst(),
                Payment.updated_at.asc(),
            )
            .limit(limit)
        )
    ).scalars().all()

    providers: dict[PaymentProvider, object] = {}
    newly_confirmed_enrollments: list[Enrollment] = []
    summary = {
        "scanned": len(payments),
        "reconciled": 0,
        "changed": 0,
        "reviews_opened": 0,
        "ignored": 0,
        "failed": 0,
        "access_notifications_sent": 0,
    }

    for payment in payments:
        lookup_id = _provider_lookup_id(payment)
        if not lookup_id:
            summary["ignored"] += 1
            continue

        had_review = bool(payment.review_required)
        try:
            async with db.begin_nested():
                provider = providers.get(payment.provider)
                if provider is None:
                    provider = await _provider_for_payment(db, tenant, payment.provider)
                    providers[payment.provider] = provider

                info = await provider.get_payment_info(lookup_id)
                summary["reconciled"] += 1
                payment.last_reconciled_at = utc_now()
                payment.last_provider_status = (info.status or "UNKNOWN")[:64]

                if info.external_reference and info.external_reference != str(payment.id):
                    payment.review_required = True
                    payment.review_reason = "periodic_reconciliation_external_reference_mismatch"
                    await ensure_payment_review(db, payment, source="periodic_reconciliation")
                    if not had_review:
                        summary["reviews_opened"] += 1
                    continue

                if info.amount is not None and abs(float(info.amount) - float(payment.amount)) >= 0.01:
                    payment.review_required = True
                    payment.review_reason = "periodic_reconciliation_amount_mismatch"
                    await ensure_payment_review(db, payment, source="periodic_reconciliation")
                    if not had_review:
                        summary["reviews_opened"] += 1
                    continue

                enrollment = None
                if payment.enrollment_id:
                    enrollment = (
                        await db.execute(
                            select(Enrollment).where(
                                Enrollment.id == payment.enrollment_id,
                                Enrollment.tenant_id == tenant_id,
                            )
                        )
                    ).scalar_one_or_none()

                action = provider_status_action(
                    payment.provider,
                    info.status,
                    (info.raw or {}).get("status_detail") if info.raw else None,
                )
                previous_status = payment.status
                previous_enrollment_status = enrollment.status if enrollment else None

                if action.kind == "normal":
                    target = action.value
                    if not isinstance(target, PaymentStatus):
                        summary["ignored"] += 1
                        continue
                    if enrollment:
                        reconcile_result = await reconcile_payment_status(payment, enrollment, target)
                        if reconcile_result.get("enrollment_newly_confirmed"):
                            newly_confirmed_enrollments.append(enrollment)
                    else:
                        payment.status = target
                        if target == PaymentStatus.APROVADO:
                            payment.paid_at = payment.paid_at or utc_now()
                elif action.kind == "special":
                    await reconcile_special_financial_event(
                        db,
                        payment,
                        enrollment,
                        str(action.value),
                    )
                else:
                    # Unknown future provider statuses are recorded but never
                    # guessed into an internal state transition.
                    summary["ignored"] += 1
                    continue

                # Explicit consistency alert independent from webhook processing.
                if (
                    enrollment
                    and payment.status == PaymentStatus.APROVADO
                    and enrollment.status == EnrollmentStatus.PENDENTE
                ):
                    payment.review_required = True
                    payment.review_reason = "approved_without_confirmed_enrollment"
                    await ensure_payment_review(db, payment, source="periodic_reconciliation")

                if payment.review_required and not had_review:
                    summary["reviews_opened"] += 1
                if payment.status != previous_status or (
                    enrollment and enrollment.status != previous_enrollment_status
                ):
                    summary["changed"] += 1
        except PaymentProviderError as exc:
            summary["failed"] += 1
            logger.warning(
                "periodic payment reconciliation provider failure",
                extra={
                    "tenant_id": str(tenant_id),
                    "payment_id": str(payment.id),
                    "provider": payment.provider.value,
                    "provider_error_code": exc.provider_error_code,
                },
            )
        except Exception:
            summary["failed"] += 1
            logger.exception(
                "unexpected periodic payment reconciliation failure",
                extra={"tenant_id": str(tenant_id), "payment_id": str(payment.id)},
            )

    tenant_settings = dict(tenant.settings or {})
    tenant_settings["last_periodic_payment_reconciliation_at"] = utc_now().isoformat()
    tenant.settings = tenant_settings
    await db.commit()

    # Mirror the B2C webhook contract: notification is an after-commit side
    # effect and can never roll back payment/enrollment state.
    seen_enrollments: set[UUID] = set()
    for enrollment in newly_confirmed_enrollments:
        if enrollment.id in seen_enrollments:
            continue
        seen_enrollments.add(enrollment.id)
        if await send_course_access_notification(db, enrollment):
            summary["access_notifications_sent"] += 1

    return summary
