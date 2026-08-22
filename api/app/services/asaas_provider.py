"""Asaas payment provider implementation.

Implements `PaymentProviderInterface` against the Asaas v3 API.
Supports PIX, BOLETO, CREDIT_CARD and UNDEFINED billing types, customer
creation/lookup, payment status queries, refunds, and webhook management.

The provider is stateless beyond the per-request API key. All HTTP
calls go through `httpx.AsyncClient` with a short timeout and raise
`PaymentProviderError` on any non-2xx response so callers can surface
a generic 502 without leaking provider details.

No live API calls are made in tests — the provider accepts an optional
``mock`` flag (or the ``ASAAS_MOCK_MODE`` setting) that returns
deterministic fake responses without touching the network.

Security:
- Every request includes an explicit User-Agent identifying the application.
- Errors are sanitized: raw response bodies are never exposed to clients.
- The API key is never logged or included in error messages.
- Authorization Bearer header is NOT used (Asaas uses access_token header).
"""

from __future__ import annotations

import logging
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
    WebhookConfig,
    WebhookListResult,
)

logger = logging.getLogger(__name__)

_SANDBOX_URL = "https://api-sandbox.asaas.com"
_PRODUCTION_URL = "https://api.asaas.com"

# Explicit User-Agent identifying the application to Asaas.
# Format: <app-name>/<version> (<runtime>; <environment>)
_USER_AGENT = "WR-Cursos/1.0.0 (Python; production)"

# Required webhook events for payment lifecycle.
# See: https://docs.asaas.com/docs/webhook-para-cobrancas
_REQUIRED_WEBHOOK_EVENTS = [
    "PAYMENT_CREATED",
    "PAYMENT_AWAITING_RISK_ANALYSIS",
    "PAYMENT_APPROVED_BY_RISK_ANALYSIS",
    "PAYMENT_REPROVED_BY_RISK_ANALYSIS",
    "PAYMENT_AUTHORIZED",
    "PAYMENT_UPDATED",
    "PAYMENT_CONFIRMED",
    "PAYMENT_RECEIVED",
    "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
    "PAYMENT_OVERDUE",
    "PAYMENT_DELETED",
    "PAYMENT_RESTORED",
    "PAYMENT_REFUNDED",
    "PAYMENT_PARTIALLY_REFUNDED",
    "PAYMENT_REFUND_IN_PROGRESS",
    "PAYMENT_REFUND_DENIED",
    "PAYMENT_CHARGEBACK_REQUESTED",
    "PAYMENT_CHARGEBACK_DISPUTE",
    "PAYMENT_AWAITING_CHARGEBACK_REVERSAL",
    "PAYMENT_RECEIVED_IN_CASH_UNDONE",
    "PAYMENT_BANK_SLIP_CANCELLED",
]

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
    def _headers(self) -> dict[str, str]:
        """Build request headers with explicit User-Agent.

        Asaas uses the ``access_token`` header (not Authorization Bearer).
        We explicitly set Content-Type and a identifiable User-Agent.
        """
        return {
            "access_token": self._api_key,
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Execute an HTTP request to the Asaas API.

        Raises PaymentProviderError with sanitized message on failure.
        Raw response bodies are NEVER included in the exception message
        — only the HTTP status code and a generic description.
        """
        if self._mock:
            return self._mock_request(method, path, json=json, params=params)

        headers = self._headers()
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method, url, json=json, params=params, headers=headers
                )
        except httpx.TimeoutException:
            raise PaymentProviderError(
                f"Asaas request timed out: {method} {path}",
                status_code=504,
                provider_error_code="timeout",
            )
        except httpx.RequestError:
            raise PaymentProviderError(
                f"Asaas request failed: {method} {path}",
                status_code=502,
                provider_error_code="connection_error",
            )

        if response.status_code >= 400:
            # Sanitize: never expose raw response body to clients.
            # Log the full error internally for debugging.
            logger.warning(
                "Asaas API error: %s %s returned %d",
                method,
                path,
                response.status_code,
            )
            # Map common status codes to safe messages
            if response.status_code == 401:
                safe_msg = "Asaas authentication failed"
                code = "invalid_access_token"
            elif response.status_code == 403:
                safe_msg = "Asaas access denied"
                code = "forbidden"
            elif response.status_code == 404:
                safe_msg = "Asaas resource not found"
                code = "not_found"
            elif response.status_code == 400:
                safe_msg = "Asaas bad request"
                code = "bad_request"
            else:
                safe_msg = f"Asaas request failed with status {response.status_code}"
                code = f"http_{response.status_code}"
            raise PaymentProviderError(
                safe_msg,
                status_code=response.status_code,
                provider_error_code=code,
            )
        return response.json()

    # ------------------------------------------------------------------
    # Checkout / charge creation
    # ------------------------------------------------------------------
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
        # Legacy compat — accepted but ignored
        enrollment_id: UUID | None = None,
    ) -> CheckoutResult:
        """Create a charge at Asaas.

        The ``externalReference`` is set to the internal Payment UUID
        (not enrollment_id) so webhook identity verification can match
        the charge back to the exact internal Payment.
        """
        if self._mock:
            return self._mock_checkout(payment_id, amount, method)

        if not customer_id:
            customer = await self.create_or_update_customer(
                name=student_name or student_email.split("@")[0],
                email=student_email,
                external_id=f"pay-{payment_id}",
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
            "externalReference": str(payment_id),
        }
        if installments and installments > 1:
            payload["installmentCount"] = installments
            payload["installmentValue"] = round(amount / installments, 2)

        result = await self._request("POST", "/v3/payments", json=payload)
        asaas_payment_id = result.get("id", "")
        # Asaas returns an invoiceUrl for boleto/PIX; for card it may be empty.
        checkout_url = result.get("invoiceUrl") or result.get("bankSlipUrl") or ""
        if not checkout_url and billing_type == "PIX":
            # Fetch the PIX QR code link.
            try:
                qr = await self._request("GET", f"/v3/payments/{asaas_payment_id}/pixQrCode")
                checkout_url = qr.get("payload") or ""
            except PaymentProviderError:
                checkout_url = ""

        return CheckoutResult(
            provider_payment_id=asaas_payment_id,
            checkout_url=checkout_url,
            raw=result,
        )

    # ------------------------------------------------------------------
    # Payment info — retrieve canonical state from Asaas
    # ------------------------------------------------------------------
    async def get_payment_info(self, provider_payment_id: str) -> PaymentInfoResult:
        """Query Asaas for the current status of a payment.

        Uses GET /v3/payments/{id} to retrieve the canonical state.
        Returns externalReference, status, value, billingType, and customer.
        """
        if self._mock:
            return self._mock_payment_info(provider_payment_id)

        result = await self._request("GET", f"/v3/payments/{provider_payment_id}")
        return PaymentInfoResult(
            provider_payment_id=provider_payment_id,
            external_reference=str(result.get("externalReference") or ""),
            status=str(result.get("status", "UNKNOWN")),
            amount=result.get("value"),
            billing_type=result.get("billingType"),
            customer_id=result.get("customer"),
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
    # Webhook management — Asaas v3 Webhooks API
    # See: https://docs.asaas.com/reference/create-new-webhook
    # ------------------------------------------------------------------
    async def list_webhooks(self) -> WebhookListResult:
        """List all webhooks configured in the Asaas account."""
        if self._mock:
            return WebhookListResult(data=[], mock=True)

        result = await self._request("GET", "/v3/webhooks")
        return WebhookListResult(
            data=result.get("data") or [],
            mock=False,
        )

    async def create_webhook(
        self,
        *,
        name: str,
        url: str,
        auth_token: str,
        email: str | None = None,
        events: list[str] | None = None,
    ) -> WebhookConfig:
        """Create a new webhook in Asaas.

        The auth_token must be 32-255 characters, not contain spaces,
        and must NOT be the Asaas API key.
        """
        if len(auth_token) < 32 or len(auth_token) > 255:
            raise PaymentProviderError(
                "Webhook auth token must be 32-255 characters",
                status_code=400,
                provider_error_code="invalid_token_length",
            )

        if self._mock:
            return WebhookConfig(
                id=f"mock-wh-{name[:10]}",
                name=name,
                url=url,
                enabled=True,
                interrupted=False,
                events=events or _REQUIRED_WEBHOOK_EVENTS,
                mock=True,
            )

        payload: dict = {
            "name": name,
            "url": url,
            "enabled": True,
            "interrupted": False,
            "apiVersion": 3,
            "authToken": auth_token,
            "sendType": "SEQUENTIALLY",
            "events": events or _REQUIRED_WEBHOOK_EVENTS,
        }
        if email:
            payload["email"] = email

        result = await self._request("POST", "/v3/webhooks", json=payload)
        return WebhookConfig(
            id=result.get("id", ""),
            name=result.get("name", name),
            url=result.get("url", url),
            enabled=result.get("enabled", True),
            interrupted=result.get("interrupted", False),
            events=result.get("events") or (events or _REQUIRED_WEBHOOK_EVENTS),
            mock=False,
        )

    async def update_webhook(
        self,
        *,
        webhook_id: str,
        name: str | None = None,
        url: str | None = None,
        auth_token: str | None = None,
        enabled: bool | None = None,
        interrupted: bool | None = None,
        events: list[str] | None = None,
    ) -> WebhookConfig:
        """Update an existing webhook in Asaas."""
        if self._mock:
            return WebhookConfig(
                id=webhook_id,
                name=name or "mock",
                url=url or "https://mock.test/webhook",
                enabled=enabled if enabled is not None else True,
                interrupted=interrupted if interrupted is not None else False,
                events=events or _REQUIRED_WEBHOOK_EVENTS,
                mock=True,
            )

        payload: dict = {}
        if name is not None:
            payload["name"] = name
        if url is not None:
            payload["url"] = url
        if auth_token is not None:
            payload["authToken"] = auth_token
        if enabled is not None:
            payload["enabled"] = enabled
        if interrupted is not None:
            payload["interrupted"] = interrupted
        if events is not None:
            payload["events"] = events
        payload["sendType"] = "SEQUENTIALLY"

        result = await self._request("POST", f"/v3/webhooks/{webhook_id}", json=payload)
        return WebhookConfig(
            id=result.get("id", webhook_id),
            name=result.get("name", name or ""),
            url=result.get("url", url or ""),
            enabled=result.get("enabled", True),
            interrupted=result.get("interrupted", False),
            events=result.get("events") or (events or _REQUIRED_WEBHOOK_EVENTS),
            mock=False,
        )

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook from Asaas."""
        if self._mock:
            return True

        try:
            await self._request("DELETE", f"/v3/webhooks/{webhook_id}")
            return True
        except PaymentProviderError as exc:
            if exc.provider_error_code == "not_found":
                return True  # Already deleted — idempotent
            raise

    async def get_webhook(self, webhook_id: str) -> WebhookConfig | None:
        """Retrieve a single webhook by ID."""
        if self._mock:
            return WebhookConfig(
                id=webhook_id,
                name="mock",
                url="https://mock.test/webhook",
                enabled=True,
                interrupted=False,
                events=_REQUIRED_WEBHOOK_EVENTS,
                mock=True,
            )

        try:
            result = await self._request("GET", f"/v3/webhooks/{webhook_id}")
        except PaymentProviderError as exc:
            if exc.provider_error_code == "not_found":
                return None
            raise
        return WebhookConfig(
            id=result.get("id", webhook_id),
            name=result.get("name", ""),
            url=result.get("url", ""),
            enabled=result.get("enabled", True),
            interrupted=result.get("interrupted", False),
            events=result.get("events") or [],
            mock=False,
        )

    async def reconcile_webhook(
        self,
        *,
        webhook_name: str,
        webhook_url: str,
        auth_token: str,
        email: str | None = None,
    ) -> WebhookConfig:
        """Reconcile a webhook: find by name, update if exists, create if not.

        This is the main entry point for the connect flow. It:
        1. Lists all webhooks.
        2. Finds one with a matching name.
        3. If found: updates URL, authToken, events, enabled=true.
        4. If not found: creates a new one.
        5. Returns the reconciled webhook config.

        Never creates duplicates on reconnect.
        """
        if self._mock:
            return await self.create_webhook(
                name=webhook_name,
                url=webhook_url,
                auth_token=auth_token,
                email=email,
            )

        # 1. List existing webhooks
        webhooks = await self.list_webhooks()
        existing = None
        for wh in webhooks.data:
            if wh.get("name") == webhook_name:
                existing = wh
                break

        if existing:
            # 2. Update existing webhook
            return await self.update_webhook(
                webhook_id=existing["id"],
                name=webhook_name,
                url=webhook_url,
                auth_token=auth_token,
                enabled=True,
                interrupted=False,
                events=_REQUIRED_WEBHOOK_EVENTS,
            )
        else:
            # 3. Create new webhook
            return await self.create_webhook(
                name=webhook_name,
                url=webhook_url,
                auth_token=auth_token,
                email=email,
            )

    # ------------------------------------------------------------------
    # Mock helpers (deterministic, no network)
    # ------------------------------------------------------------------
    def _mock_request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Deterministic mock responses for tests."""
        if method == "GET" and path == "/v3/customers":
            return {"data": [], "totalCount": 0}
        if method == "GET" and path.startswith("/v3/payments/"):
            pid = path.split("/")[-1]
            if pid == "pixQrCode":
                return {"payload": f"mock-pix-payload-{pid}", "encodedImage": "mock"}
            return {
                "id": pid,
                "status": "RECEIVED",
                "value": 100.0,
                "externalReference": pid.replace("mock-pay-", ""),
                "billingType": "PIX",
                "customer": "mock-cus-1",
                "mock": True,
            }
        if method == "GET" and path == "/v3/webhooks":
            return {"data": [], "totalCount": 0}
        if method == "POST" and path == "/v3/webhooks":
            return {
                "id": f"mock-wh-{(json or {}).get('name', 'unknown')[:10]}",
                "name": (json or {}).get("name", ""),
                "url": (json or {}).get("url", ""),
                "enabled": True,
                "interrupted": False,
                "events": (json or {}).get("events", []),
            }
        if method == "POST" and path.startswith("/v3/webhooks/"):
            return {
                "id": path.split("/")[-1],
                "name": (json or {}).get("name", ""),
                "url": (json or {}).get("url", ""),
                "enabled": (json or {}).get("enabled", True),
                "interrupted": (json or {}).get("interrupted", False),
                "events": (json or {}).get("events", []),
            }
        if method == "DELETE" and path.startswith("/v3/webhooks/"):
            return {"deleted": True}
        return {"mock": True, "method": method, "path": path}

    def _mock_checkout(
        self, payment_id: UUID, amount: float, method: PaymentMethod
    ) -> CheckoutResult:
        billing = _METHOD_TO_BILLING.get(method, "UNDEFINED")
        pid = f"mock-pay-{payment_id}"
        return CheckoutResult(
            provider_payment_id=pid,
            checkout_url=f"http://mock-asaas.test/checkout/{payment_id}?billing={billing}",
            raw={
                "id": pid,
                "mock": True,
                "value": amount,
                "billingType": billing,
                "externalReference": str(payment_id),
            },
        )

    def _mock_payment_info(self, provider_payment_id: str) -> PaymentInfoResult:
        # Extract payment_id from mock-pay-{payment_id}
        prefix = "mock-pay-"
        ext_ref = provider_payment_id.removeprefix(prefix)
        return PaymentInfoResult(
            provider_payment_id=provider_payment_id,
            external_reference=ext_ref,
            status="RECEIVED",
            amount=100.0,
            billing_type="PIX",
            customer_id="mock-cus-1",
            raw={"id": provider_payment_id, "status": "RECEIVED", "mock": True},
        )


__all__ = [
    "_REQUIRED_WEBHOOK_EVENTS",
    "AsaasProvider",
]
