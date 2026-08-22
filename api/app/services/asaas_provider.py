"""Asaas payment provider implementation.

Implements `PaymentProviderInterface` against the Asaas v3 API.
Supports PIX, BOLETO, CREDIT_CARD and UNDEFINED billing types, customer
creation/lookup, payment status queries, and refunds.

The provider is stateless beyond the per-request API key. All HTTP
calls go through `httpx.AsyncClient` with a short timeout and raise
`PaymentProviderError` on any non-2xx response so callers can surface
a generic 502 without leaking provider details.

No live API calls are made in tests — the provider accepts an optional
``mock`` flag (or the ``ASAAS_MOCK_MODE`` setting) that returns
deterministic fake responses without touching the network.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx

from app.core.config import settings
from app.models.payment import PaymentMethod, PaymentProvider
from app.services.payment_provider_base import (
    CheckoutResult,
    CustomerResult,
    PaymentInfoResult,
    PaymentProviderError,
)

_SANDBOX_URL = "https://api-sandbox.asaas.com"
_PRODUCTION_URL = "https://api.asaas.com"

# Asaas payment status → our internal PaymentStatus mapping lives in
# the webhook route, but we expose the raw status string here.
# See: https://docs.asaas.com/docs/payment-events
ASAAS_STATUS_MAP = {
    "PENDING": "PENDING",
    "RECEIVED": "RECEIVED",
    "CONFIRMED": "CONFIRMED",
    "OVERDUE": "OVERDUE",
    "REFUNDED": "REFUNDED",
    "REFUND_REQUESTED": "REFUND_REQUESTED",
    "CHARGEBACK_REQUESTED": "CHARGEBACK_REQUESTED",
    "CHARGEBACK_DISPUTE": "CHARGEBACK_DISPUTE",
    "AWAITING_CHARGEBACK": "AWAITING_CHARGEBACK",
    "FAILED": "FAILED",
    "DONE": "DONE",
}

# Map our PaymentMethod → Asaas billingType.
_METHOD_TO_BILLING = {
    PaymentMethod.PIX: "PIX",
    PaymentMethod.BOLETO: "BOLETO",
    PaymentMethod.CARTAO: "CREDIT_CARD",
    PaymentMethod.UNDEFINED: "UNDEFINED",
}


class AsaasProvider:
    """Asaas v3 API adapter implementing PaymentProviderInterface."""

    provider = PaymentProvider.ASAAS

    def __init__(
        self,
        api_key: str,
        sandbox: bool = False,
        mock: bool | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._sandbox = sandbox
        self._mock = mock if mock is not None else getattr(settings, "ASAAS_MOCK_MODE", False)
        self._timeout = timeout
        self._base_url = _SANDBOX_URL if sandbox else _PRODUCTION_URL

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        headers = {
            "access_token": self._api_key,
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method, url, json=json, params=params, headers=headers
            )
        if response.status_code >= 400:
            raise PaymentProviderError(
                f"Asaas {method} {path} failed: {response.status_code} {response.text}"
            )
        return response.json()

    # ------------------------------------------------------------------
    # Checkout / charge creation
    # ------------------------------------------------------------------
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
        if self._mock:
            return self._mock_checkout(enrollment_id, amount, method)

        if not customer_id:
            customer = await self.create_or_update_customer(
                name=student_name or student_email.split("@")[0],
                email=student_email,
                external_id=str(enrollment_id),
            )
            customer_id = customer.provider_customer_id

        due_date = (datetime.now(UTC) + timedelta(days=3)).strftime("%Y-%m-%d")
        billing_type = _METHOD_TO_BILLING.get(method, "UNDEFINED")

        payload: dict = {
            "customer": customer_id,
            "billingType": billing_type,
            "value": amount,
            "dueDate": due_date,
            "description": course_name,
            "externalReference": str(enrollment_id),
        }
        if installments and installments > 1:
            payload["installmentCount"] = installments
            payload["installmentValue"] = round(amount / installments, 2)

        result = await self._request("POST", "/v3/payments", json=payload)
        payment_id = result.get("id", "")
        # Asaas returns an invoiceUrl for boleto/PIX; for card it may be empty.
        checkout_url = result.get("invoiceUrl") or result.get("bankSlipUrl") or ""
        if not checkout_url and billing_type == "PIX":
            # Fetch the PIX QR code link.
            try:
                qr = await self._request("GET", f"/v3/payments/{payment_id}/pixQrCode")
                checkout_url = qr.get("payload") or ""
            except PaymentProviderError:
                checkout_url = ""

        return CheckoutResult(
            provider_payment_id=payment_id,
            checkout_url=checkout_url,
            raw=result,
        )

    # ------------------------------------------------------------------
    # Payment info
    # ------------------------------------------------------------------
    async def get_payment_info(self, provider_payment_id: str) -> PaymentInfoResult:
        if self._mock:
            return self._mock_payment_info(provider_payment_id)

        result = await self._request("GET", f"/v3/payments/{provider_payment_id}")
        return PaymentInfoResult(
            provider_payment_id=provider_payment_id,
            external_reference=str(result.get("externalReference") or ""),
            status=str(result.get("status", "UNKNOWN")),
            amount=result.get("value"),
            raw=result,
        )

    # ------------------------------------------------------------------
    # Refund
    # ------------------------------------------------------------------
    async def refund_payment(self, provider_payment_id: str) -> dict:
        if self._mock:
            return {"id": provider_payment_id, "status": "REFUNDED", "mock": True}

        return await self._request("POST", f"/v3/payments/{provider_payment_id}/refund")

    # ------------------------------------------------------------------
    # Customer
    # ------------------------------------------------------------------
    async def create_or_update_customer(
        self,
        *,
        name: str,
        email: str,
        cpf_cnpj: str | None = None,
        phone: str | None = None,
        external_id: str | None = None,
    ) -> CustomerResult:
        if self._mock:
            return CustomerResult(
                provider_customer_id=f"mock-cus-{external_id or email}",
                raw={"mock": True},
            )

        # Try to find an existing customer by externalReference first to
        # avoid duplicates (Asaas allows duplicates by design).
        if external_id:
            existing = await self._request(
                "GET",
                "/v3/customers",
                params={"externalReference": external_id, "limit": 1},
            )
            data_list = existing.get("data") or []
            if data_list:
                return CustomerResult(
                    provider_customer_id=data_list[0]["id"],
                    raw=data_list[0],
                )

        payload: dict = {
            "name": name,
            "email": email,
            "notificationDisabled": False,
        }
        if cpf_cnpj:
            payload["cpfCnpj"] = cpf_cnpj
        if phone:
            payload["mobilePhone"] = phone
        if external_id:
            payload["externalReference"] = external_id

        result = await self._request("POST", "/v3/customers", json=payload)
        return CustomerResult(
            provider_customer_id=result.get("id", ""),
            raw=result,
        )

    # ------------------------------------------------------------------
    # Mock helpers (deterministic, no network)
    # ------------------------------------------------------------------
    def _mock_checkout(
        self, enrollment_id: UUID, amount: float, method: PaymentMethod
    ) -> CheckoutResult:
        billing = _METHOD_TO_BILLING.get(method, "UNDEFINED")
        pid = f"mock-pay-{enrollment_id}"
        return CheckoutResult(
            provider_payment_id=pid,
            checkout_url=f"http://mock-asaas.test/checkout/{enrollment_id}?billing={billing}",
            raw={"id": pid, "mock": True, "value": amount, "billingType": billing},
        )

    def _mock_payment_info(self, provider_payment_id: str) -> PaymentInfoResult:
        # Extract enrollment_id from mock-pay-{enrollment_id}
        prefix = "mock-pay-"
        ext_ref = provider_payment_id.removeprefix(prefix)
        return PaymentInfoResult(
            provider_payment_id=provider_payment_id,
            external_reference=ext_ref,
            status="RECEIVED",
            amount=None,
            raw={"id": provider_payment_id, "status": "RECEIVED", "mock": True},
        )


__all__ = ["ASAAS_STATUS_MAP", "AsaasProvider"]
