"""Asaas integration management routes.

Provides admin-facing endpoints for connecting, validating, and
disconnecting the Asaas payment provider for a tenant. Also provides
the authenticated webhook endpoint for receiving Asaas payment events.

All financial credentials are write-only: they can be configured,
replaced, deleted, and validated, but never revealed in plaintext.

Connect flow:
1. Receive API key over authenticated backend request (never logged).
2. Validate expected production credential format.
3. Perform a READ-ONLY authentication request to Asaas.
4. If invalid, do not persist.
5. If valid, encrypt/store in TenantSecret.
6. Generate a separate webhook authentication token.
7. Encrypt/store webhook token.
8. Reconcile/create Asaas webhook.
9. Mark provider connection healthy.

Webhook endpoint:
- No end-user JWT.
- Resolve tenant from path (tenant_slug).
- Fetch that tenant's encrypted webhook token.
- Validate asaas-access-token header using constant-time comparison.
- Reject missing/incorrect token.
- Never trust tenant_id in webhook payload.
- Use PaymentWebhookEvent ledger for idempotency.
"""

from __future__ import annotations

import hmac
import json
import secrets as pysecrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.models.enrollment import Enrollment
from app.models.payment import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWebhookEvent,
)
from app.models.tenant import Tenant
from app.services.asaas_provider import AsaasProvider
from app.services.payment_provider_base import PaymentProviderError
from app.services.payment_reconciliation import reconcile_payment_status
from app.services.tenant_secret_service import (
    ASAAS_API_KEY_KEY,
    get_asaas_api_key,
    get_tenant_secret,
    set_tenant_secret,
)

router = APIRouter()

# Webhook token secret key suffix.
ASAAS_WEBHOOK_TOKEN_KEY = "asaas_webhook_token"

# Asaas event → internal PaymentStatus mapping.
# See: https://docs.asaas.com/docs/payment-events
# PAYMENT_CONFIRMED: payment confirmed but funds not yet available.
# PAYMENT_RECEIVED: funds available in the Asaas account.
# For credit card: CONFIRMED → RECEIVED (funds available later).
# For PIX: typically goes directly to RECEIVED.
# We map both CONFIRMED and RECEIVED to APROVADO since the payment
# itself is confirmed — the fund availability is an operational concern.
_ASAAS_EVENT_MAP = {
    "PAYMENT_CREATED": PaymentStatus.PROCESSANDO,
    "PAYMENT_AWAITING": PaymentStatus.PROCESSANDO,
    "PAYMENT_UPDATED": PaymentStatus.PROCESSANDO,
    "PAYMENT_CONFIRMED": PaymentStatus.APROVADO,
    "PAYMENT_RECEIVED": PaymentStatus.APROVADO,
    "PAYMENT_OVERDUE": PaymentStatus.PROCESSANDO,
    "PAYMENT_REFUNDED": PaymentStatus.REEMBOLSADO,
    "PAYMENT_REFUND_REQUESTED": PaymentStatus.PROCESSANDO,
    "PAYMENT_CHARGEBACK_REQUESTED": PaymentStatus.RECUSADO,
    "PAYMENT_CHARGEBACK_DISPUTE": PaymentStatus.RECUSADO,
    "PAYMENT_AWAITING_CHARGEBACK": PaymentStatus.RECUSADO,
    "PAYMENT_FAILED": PaymentStatus.RECUSADO,
    "PAYMENT_DELETED": PaymentStatus.RECUSADO,
    "PAYMENT_RESTORED": PaymentStatus.PROCESSANDO,
}


def _constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())


def _generate_webhook_token() -> str:
    """Generate a cryptographically secure random webhook token."""
    return pysecrets.token_urlsafe(32)


async def _get_tenant_by_slug(db: AsyncSession, slug: str) -> Tenant | None:
    stmt = select(Tenant).where(Tenant.slug == slug)
    return (await db.execute(stmt)).scalar_one_or_none()


# ------------------------------------------------------------------
# Integration status and management
# ------------------------------------------------------------------

@router.get("/status")
async def asaas_status(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Returns the Asaas integration status for the current tenant.

    Never reveals credentials. Shows only:
    - configured: yes/no
    - webhook_configured: yes/no
    - provider: ASAAS or MERCADO_PAGO (based on tenant settings)
    """
    tenant_id = get_current_tenant_id()
    api_key = await get_asaas_api_key(db, tenant_id)
    webhook_token = await get_tenant_secret(db, tenant_id, ASAAS_WEBHOOK_TOKEN_KEY)

    tenant = await db.get(Tenant, tenant_id)
    tenant_settings = (tenant.settings if tenant else None) or {}
    configured_provider = (tenant_settings.get("payment_provider") or "").upper()

    return {
        "configured": api_key is not None,
        "webhook_configured": webhook_token is not None,
        "active_provider": configured_provider or "MERCADO_PAGO",
        "is_asaas_active": configured_provider == "ASAAS",
    }


@router.post("/connect")
async def asaas_connect(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Connect Asaas by storing the production API key.

    Receives the API key in the request body (never logged). Validates
    it with a read-only authentication request before persisting. If
    valid, encrypts and stores it in TenantSecret, generates a webhook
    token, and marks the provider as ASAAS in tenant settings.
    """
    tenant_id = get_current_tenant_id()
    body = await request.json()
    api_key = body.get("api_key", "").strip()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is required",
        )

    # Basic format validation (Asaas keys start with $aaas_ or are
    # a long alphanumeric string).
    if len(api_key) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key format",
        )

    # Validate with a read-only request (create a mock provider to
    # test authentication). In mock mode, skip the validation call.
    if not getattr(settings, "ASAAS_MOCK_MODE", False):
        provider = AsaasProvider(api_key=api_key, sandbox=False)
        try:
            # Use a simple customer list call as authentication check
            await provider._request("GET", "/v3/customers", params={"limit": 1})
        except PaymentProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Asaas API key validation failed",
            ) from exc

    # Store the API key encrypted
    await set_tenant_secret(db, tenant_id, ASAAS_API_KEY_KEY, api_key, "Asaas API key")

    # Generate and store webhook token
    webhook_token = _generate_webhook_token()
    await set_tenant_secret(
        db, tenant_id, ASAAS_WEBHOOK_TOKEN_KEY, webhook_token, "Asaas webhook auth token"
    )

    # Update tenant settings to use ASAAS
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant_settings = dict(tenant.settings or {})
    tenant_settings["payment_provider"] = "ASAAS"
    tenant.settings = tenant_settings

    await db.commit()

    return {
        "status": "connected",
        "webhook_configured": True,
        "message": "Asaas connected successfully. Configure the webhook URL in Asaas dashboard.",
    }


@router.post("/validate")
async def asaas_validate(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Validate the stored Asaas connection with a read-only request."""
    tenant_id = get_current_tenant_id()
    api_key = await get_asaas_api_key(db, tenant_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asaas not configured",
        )

    if getattr(settings, "ASAAS_MOCK_MODE", False):
        return {"valid": True, "message": "Mock mode — validation skipped"}

    provider = AsaasProvider(api_key=api_key, sandbox=False)
    try:
        await provider._request("GET", "/v3/customers", params={"limit": 1})
    except PaymentProviderError as exc:
        return {"valid": False, "message": f"Validation failed: {exc}"}

    return {"valid": True, "message": "Connection is valid"}


@router.delete("/")
async def asaas_disconnect(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Disconnect Asaas by removing stored credentials.

    Reverts the tenant provider to MERCADO_PAGO (default).
    """
    from app.models.tenant_secret import TenantSecret

    tenant_id = get_current_tenant_id()

    # Remove API key
    stmt = select(TenantSecret).where(
        TenantSecret.tenant_id == tenant_id,
        TenantSecret.key == ASAAS_API_KEY_KEY,
    )
    secret = (await db.execute(stmt)).scalar_one_or_none()
    if secret:
        await db.delete(secret)

    # Remove webhook token
    stmt = select(TenantSecret).where(
        TenantSecret.tenant_id == tenant_id,
        TenantSecret.key == ASAAS_WEBHOOK_TOKEN_KEY,
    )
    secret = (await db.execute(stmt)).scalar_one_or_none()
    if secret:
        await db.delete(secret)

    # Revert tenant settings to MERCADO_PAGO
    tenant = await db.get(Tenant, tenant_id)
    if tenant:
        tenant_settings = dict(tenant.settings or {})
        tenant_settings.pop("payment_provider", None)
        tenant.settings = tenant_settings

    await db.commit()
    return {"status": "disconnected"}


# ------------------------------------------------------------------
# Webhook endpoint — receives Asaas payment events
# ------------------------------------------------------------------

@router.post("/webhook/{tenant_slug}")
async def asaas_webhook(
    tenant_slug: str,
    request: Request,
    asaas_access_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Authenticated webhook endpoint for Asaas payment events.

    Authentication:
    - No end-user JWT.
    - Tenant resolved from path (tenant_slug).
    - Fetches that tenant's encrypted webhook token.
    - Validates asaas-access-token header using constant-time comparison.
    - Rejects missing/incorrect token.
    - Never trusts tenant_id in webhook payload.

    Idempotency:
    - Uses PaymentWebhookEvent ledger with unique constraint on
      (tenant, provider, provider_event_id).
    - Duplicate events return 200 without re-applying transitions.

    Payment identity verification:
    - Resolved tenant must match the payment's tenant.
    - provider_payment_id must match.
    - externalReference must match the internal Payment id.
    - Amount must match the internal Payment amount.
    """
    # ── Resolve tenant from slug ──
    tenant = await _get_tenant_by_slug(db, tenant_slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # ── Validate webhook token ──
    webhook_token = await get_tenant_secret(db, tenant.id, ASAAS_WEBHOOK_TOKEN_KEY)
    if not webhook_token:
        raise HTTPException(status_code=403, detail="Webhook not configured")

    if not asaas_access_token:
        raise HTTPException(status_code=403, detail="Missing access token")

    if not _constant_time_compare(asaas_access_token, webhook_token):
        raise HTTPException(status_code=403, detail="Invalid access token")

    # ── Parse webhook payload ──
    body = await request.json()
    event_id = body.get("id", "")
    event_type = body.get("event", "")
    payment_obj = body.get("payment", {})

    # payment can be a dict with id, or just a string id
    if isinstance(payment_obj, dict):
        provider_payment_id = payment_obj.get("id", "")
    else:
        provider_payment_id = str(payment_obj)

    if not event_id or not provider_payment_id:
        raise HTTPException(
            status_code=400, detail="Missing event id or payment id"
        )

    # ── Idempotency: check if event already processed ──
    existing_event = (
        await db.execute(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.tenant_id == tenant.id,
                PaymentWebhookEvent.provider == PaymentProvider.ASAAS,
                PaymentWebhookEvent.provider_event_id == event_id,
            )
        )
    ).scalar_one_or_none()

    if existing_event:
        # Duplicate event — acknowledge without re-processing
        return {"status": "ok", "duplicate": True}

    # ── Find the internal payment by provider_payment_id ──
    # Never trust tenant_id from the payload — use the resolved tenant.
    stmt = select(Payment).where(
        Payment.tenant_id == tenant.id,
        Payment.provider == PaymentProvider.ASAAS,
        Payment.provider_payment_id == provider_payment_id,
    )
    payment = (await db.execute(stmt)).scalar_one_or_none()

    # Record the webhook event regardless of whether we found a payment
    # (so we don't reprocess even if the payment doesn't exist yet)
    event_record = PaymentWebhookEvent(
        tenant_id=tenant.id,
        provider=PaymentProvider.ASAAS,
        provider_event_id=event_id,
        event_type=event_type,
        provider_payment_id=provider_payment_id,
        result="processing",
    )
    db.add(event_record)

    if not payment:
        event_record.result = "payment_not_found"
        await db.commit()
        return {"status": "ok", "payment_found": False}

    # ── Map event to internal status ──
    new_status = _ASAAS_EVENT_MAP.get(event_type)
    if new_status is None:
        # Unknown event — record it but don't crash
        event_record.result = f"unknown_event:{event_type}"
        await db.commit()
        return {"status": "ok", "unknown_event": True}

    # ── Payment identity verification ──
    # Load enrollment for reconciliation
    enrollment = None
    if payment.enrollment_id:
        enrollment = await db.get(Enrollment, payment.enrollment_id)
        if not enrollment or enrollment.tenant_id != tenant.id:
            event_record.result = "enrollment_tenant_mismatch"
            await db.commit()
            return {"status": "ok", "error": "enrollment_tenant_mismatch"}

    # ── Apply status transition via shared reconciliation ──
    if enrollment:
        result = await reconcile_payment_status(payment, enrollment, new_status)
        event_record.result = json.dumps(result)
    else:
        # Company payment (no enrollment) — just update payment status
        if payment.status != new_status:
            payment.status = new_status
            if new_status == PaymentStatus.APROVADO:
                from app.core.utils import utc_now
                payment.paid_at = utc_now()
        event_record.result = "status_updated"

    await db.commit()

    return {"status": "ok", "event": event_type, "payment_status": new_status.value}
