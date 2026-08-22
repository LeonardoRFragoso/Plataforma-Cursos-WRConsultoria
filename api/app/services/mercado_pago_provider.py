"""Mercado Pago payment provider implementation.

Wraps the existing `MercadoPagoService` to satisfy the
`PaymentProviderInterface` contract. This is a thin adapter — the
underlying HTTP logic stays in `mercado_pago_service.py` to preserve
backward compatibility with the webhook route and tests.
"""

from __future__ import annotations

from uuid import UUID

from app.models.payment import PaymentMethod, PaymentProvider
from app.services.mercado_pago_service import MercadoPagoError, MercadoPagoService
from app.services.payment_provider_base import (
    CheckoutResult,
    CustomerResult,
    PaymentInfoResult,
    PaymentProviderError,
)


class MercadoPagoProvider:
    """Mercado Pago adapter implementing PaymentProviderInterface."""

    provider = PaymentProvider.MERCADO_PAGO

    def __init__(self, access_token: str | None = None) -> None:
        self._access_token = access_token

    async def create_checkout(
        self,
        *,
        enrollment_id: UUID,
        amount: float,
        student_email: str,
        student_name: str | None,
        course_name: str,
        method: PaymentMethod,
        installments: int | None = None,
        customer_id: str | None = None,
    ) -> CheckoutResult:
        try:
            preference = await MercadoPagoService.create_preference(
                enrollment_id=str(enrollment_id),
                amount=amount,
                student_email=student_email,
                course_name=course_name,
                access_token=self._access_token,
            )
        except MercadoPagoError as exc:
            raise PaymentProviderError(str(exc)) from exc

        return CheckoutResult(
            provider_payment_id=preference.get("id", ""),
            checkout_url=preference.get("init_point", ""),
            raw=preference,
        )

    async def get_payment_info(self, provider_payment_id: str) -> PaymentInfoResult:
        try:
            info = await MercadoPagoService.get_payment_info(
                provider_payment_id, self._access_token
            )
        except MercadoPagoError as exc:
            raise PaymentProviderError(str(exc)) from exc

        return PaymentInfoResult(
            provider_payment_id=provider_payment_id,
            external_reference=str(info.get("external_reference") or ""),
            status=str(info.get("status", "unknown")),
            amount=info.get("transaction_amount"),
            raw=info,
        )

    async def refund_payment(self, provider_payment_id: str) -> dict:
        try:
            return await MercadoPagoService.refund_payment(
                provider_payment_id, self._access_token
            )
        except MercadoPagoError as exc:
            raise PaymentProviderError(str(exc)) from exc

    async def create_or_update_customer(
        self,
        *,
        name: str,
        email: str,
        cpf_cnpj: str | None = None,
        phone: str | None = None,
        external_id: str | None = None,
    ) -> CustomerResult:
        # Mercado Pago does not require an explicit customer object for
        # the preference-based checkout flow. Return a deterministic
        # placeholder so callers can store it without special-casing.
        return CustomerResult(provider_customer_id=f"mp-email:{email}", raw={})
