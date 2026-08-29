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

Security:
- PaymentProviderError carries only sanitized, safe messages.
- Raw provider response bodies are NEVER exposed to clients.
- Internal logging may include HTTP status and error codes, but never
  credentials, API keys, or customer PII.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as _settings
from app.models.payment import PaymentMethod, PaymentProvider


class PaymentProviderError(Exception):
    """Sanitized error raised by any payment provider implementation.

    The ``message`` is safe to return to clients — it never contains
    raw provider response bodies, API keys, or customer data.

    Attributes:
        status_code: The HTTP status code from the provider (if applicable).
        provider_error_code: A safe, non-sensitive error code from the provider.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider_error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_error_code = provider_error_code

    @property
    def safe_message(self) -> str:
        """Message safe to return to HTTP clients."""
        return str(self.args[0]) if self.args else "Provider error"


@dataclass(frozen=True)
class CheckoutResult:
    """Normalized result of creating a checkout/charge with a provider."""

    provider_payment_id: str
    checkout_url: str
    raw: dict


@dataclass(frozen=True)
class PaymentInfoResult:
    """Normalized result of querying a payment's status from a provider.

    Includes externalReference, status, amount, billingType, and customer
    for webhook identity verification.
    """

    provider_payment_id: str
    external_reference: str
    status: str  # raw provider status string
    amount: float | None = None
    billing_type: str | None = None
    customer_id: str | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class CustomerResult:
    """Normalized result of creating/looking up a customer at a provider."""

    provider_customer_id: str
    raw: dict


@dataclass(frozen=True)
class WebhookConfig:
    """Normalized webhook configuration from the provider."""

    id: str
    name: str
    url: str
    enabled: bool
    interrupted: bool
    events: list[str]
    mock: bool = False


@dataclass(frozen=True)
class WebhookListResult:
    """Normalized result of listing webhooks from the provider."""

    data: list[dict]
    mock: bool = False


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
        payment_id: UUID,
        amount: float,
        student_email: str,
        student_name: str | None,
        course_name: str,
        method: PaymentMethod,
        installments: int | None = None,
        customer_id: str | None = None,
        enrollment_id: UUID | None = None,
    ) -> CheckoutResult:
        """Create a charge/checkout at the provider.

        The ``externalReference`` MUST be set to the internal Payment UUID
        (``str(payment_id)``) so webhook identity verification can match
        the charge back to the exact internal Payment.

        Returns a normalized CheckoutResult. Raises PaymentProviderError
        on any provider-side failure.
        """
        ...

    async def get_payment_info(self, provider_payment_id: str) -> PaymentInfoResult:
        """Query the provider for the current status of a payment.

        Returns externalReference, status, amount, billingType, and customer
        for webhook identity verification.
        """
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
    1. ``tenant.settings["payment_provider"]`` if set, recognized, AND
       in ``PAYMENT_PROVIDERS_ENABLED``. If the tenant selects a provider
       that is not enabled, fails closed with an error (does NOT fall
       back to another provider silently).
    2. ``PAYMENT_PROVIDER`` global default (must also be enabled).

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

    enabled_providers = _settings.payment_providers_enabled_list

    settings = tenant_settings or {}
    configured = (settings.get("payment_provider") or "").upper()
    if not configured:
        configured = _settings.PAYMENT_PROVIDER.upper()

    # Fail closed: if the tenant selected a provider that is not enabled,
    # raise an error. Do NOT silently fall back to another provider.
    if configured not in enabled_providers:
        raise PaymentProviderError(
            f"Payment provider '{configured}' is not enabled for this deployment. "
            f"Enabled providers: {', '.join(enabled_providers)}. "
            f"Tenant cannot use a provider that is not explicitly enabled.",
            status_code=403,
            provider_error_code="provider_not_enabled",
        )

    if configured == PaymentProvider.ASAAS.value:
        api_key = await get_asaas_api_key(db, tenant_id)
        if not api_key:
            raise PaymentProviderError(
                "Asaas configured for tenant but no asaas_api_key secret found",
                status_code=400,
                provider_error_code="missing_api_key",
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
    "WebhookConfig",
    "WebhookListResult",
    "resolve_provider",
]
