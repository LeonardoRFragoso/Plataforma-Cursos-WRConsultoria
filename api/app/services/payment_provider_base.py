"""Payment provider abstraction layer.

Defines a uniform interface that every payment gateway (Mercado Pago,
Asaas, etc.) must implement. The route layer and reconciliation service
interact with providers exclusively through this interface, so adding a
new gateway never requires touching route code.

A provider instance is constructed per-request with the tenant's
decrypted credentials and is stateless beyond those credentials.

The factory (`resolve_provider`) reads the tenant's configured provider
from `tenant.settings["payment_provider"]` (defaulting to
``MERCADO_PAGO`` for backward compatibility) and instantiates the
matching service with credentials fetched from `TenantSecret`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import PaymentMethod, PaymentProvider


class PaymentProviderError(Exception):
    """Base error raised by any payment provider implementation."""


@dataclass(frozen=True)
class CheckoutResult:
    """Normalized result of creating a checkout/charge with a provider."""

    provider_payment_id: str
    checkout_url: str
    raw: dict


@dataclass(frozen=True)
class PaymentInfoResult:
    """Normalized result of querying a payment's status from a provider."""

    provider_payment_id: str
    external_reference: str
    status: str  # raw provider status string
    amount: float | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class CustomerResult:
    """Normalized result of creating/looking up a customer at a provider."""

    provider_customer_id: str
    raw: dict


class PaymentProviderInterface(Protocol):
    """Uniform contract every payment gateway must satisfy.

    Implementations MUST be safe to instantiate per-request with only
    the tenant's credentials. They MUST NOT cache credentials or
    payment state across requests.
    """

    provider: PaymentProvider

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
        """Create a charge/checkout at the provider.

        Returns a normalized CheckoutResult. Raises PaymentProviderError
        on any provider-side failure.
        """
        ...

    async def get_payment_info(self, provider_payment_id: str) -> PaymentInfoResult:
        """Query the provider for the current status of a payment."""
        ...

    async def refund_payment(self, provider_payment_id: str) -> dict:
        """Refund a payment at the provider. Returns raw provider response."""
        ...

    async def create_or_update_customer(
        self,
        *,
        name: str,
        email: str,
        cpf_cnpj: str | None = None,
        phone: str | None = None,
        external_id: str | None = None,
    ) -> CustomerResult:
        """Create or update a customer at the provider.

        Not all providers support an explicit customer object; those
        that don't may return a deterministic placeholder.
        """
        ...


async def resolve_provider(
    db: AsyncSession,
    tenant_id: UUID,
    tenant_settings: dict | None = None,
) -> PaymentProviderInterface:
    """Resolve the active payment provider for a tenant.

    Selection order:
    1. ``tenant.settings["payment_provider"]`` if set and recognized.
    2. ``MERCADO_PAGO`` (legacy default).

    Credentials are fetched from `TenantSecret` (encrypted). Falls back
    to legacy ``tenant.settings["mp_access_token"]`` for Mercado Pago
    during the migration window.
    """
    from app.services.asaas_provider import AsaasProvider
    from app.services.mercado_pago_provider import MercadoPagoProvider
    from app.services.tenant_secret_service import (
        get_asaas_api_key,
        get_mercado_pago_access_token,
    )

    settings = tenant_settings or {}
    configured = (settings.get("payment_provider") or "").upper()

    if configured == PaymentProvider.ASAAS.value:
        api_key = await get_asaas_api_key(db, tenant_id)
        if not api_key:
            raise PaymentProviderError(
                "Asaas configured for tenant but no asaas_api_key secret found"
            )
        return AsaasProvider(api_key=api_key, sandbox=settings.get("asaas_sandbox", False))

    # Default: Mercado Pago
    access_token = await get_mercado_pago_access_token(db, tenant_id)
    if not access_token:
        access_token = settings.get("mp_access_token")
    return MercadoPagoProvider(access_token=access_token)


__all__ = [
    "CheckoutResult",
    "CustomerResult",
    "PaymentInfoResult",
    "PaymentProviderError",
    "PaymentProviderInterface",
    "resolve_provider",
]
