"""Asaas integration management routes.

Provides admin-facing endpoints for connecting, validating, and
disconnecting the Asaas payment provider for a tenant. Also provides
the authenticated webhook endpoint for receiving Asaas payment events.

All financial credentials are write-only: they can be configured,
replaced, deleted, and validated, but never revealed in plaintext.

Connect flow (all steps must succeed before returning "connected"):
1. Receive API key over authenticated backend request (never logged).
2. Validate production key format ($aact_prod_ prefix in production).
3. Perform a READ-ONLY authentication request to Asaas.
4. If invalid, do not persist.
5. If valid, encrypt/store API key in TenantSecret.
6. Generate a separate webhook authentication token (NOT the API key).
7. Encrypt/store webhook token in TenantSecret.
8. Resolve production callback URL from trusted backend configuration.
9. Reconcile/create Asaas webhook via API (list → update or create).
10. Verify webhook exists, URL matches, authToken matches, events configured.
11. Verify webhook is enabled and not interrupted.
12. Store webhook metadata (webhook_id, enabled, interrupted) in tenant settings.
13. Mark provider connection healthy.

Webhook endpoint:
- No end-user JWT.
- Resolve tenant from path (tenant_slug).
- Fetch that tenant's encrypted webhook token.
- Validate asaas-access-token header using constant-time comparison.
- Reject missing/incorrect token.
- Never trust tenant_id in webhook payload.
- Use PaymentWebhookEvent ledger for idempotency with state machine.
- Validate payment identity: provider_payment_id, externalReference,
  amount, and provider customer (via GET /v3/payments/{id} retrieval).
- Event state machine: RECEIVED → PENDING_MATCH → PROCESSED | IGNORED | FAILED.
- Only PROCESSED prevents future reconciliation (terminal success).
- PENDING_MATCH allows retry (payment may not exist yet).
- Handle concurrent duplicate webhook requests via IntegrityError catch.
"""

from __future__ import annotations

import hmac
import json
import logging
import secrets as pysecrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin, get_current_tenant_id
from app.core.utils import utc_now
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

logger = logging.getLogger(__name__)

router = APIRouter()

# Secret keys in TenantSecret.
ASAAS_WEBHOOK_TOKEN_KEY = "asaas_webhook_token"

# Webhook event processing states (state machine).
EVENT_STATE_RECEIVED = "RECEIVED"
EVENT_STATE_PENDING_MATCH = "PENDING_MATCH"
EVENT_STATE_PROCESSED = "PROCESSED"
EVENT_STATE_IGNORED = "IGNORED"
EVENT_STATE_FAILED = "FAILED"

# Terminal states that prevent future reconciliation.
# Results are stored as "STATE" or "STATE:detail", so we check prefixes.
_TERMINAL_STATE_PREFIXES = (
    EVENT_STATE_PROCESSED,
    EVENT_STATE_IGNORED,
)


def _is_terminal_state(result: str) -> bool:
    """Check if an event result is terminal (prevents future reconciliation)."""
    return any(result == prefix or result.startswith(f"{prefix}:") for prefix in _TERMINAL_STATE_PREFIXES)

# Asaas event → internal PaymentStatus mapping.
# Based on official Asaas documentation:
# https://docs.asaas.com/docs/webhook-para-cobrancas
#
# Payment lifecycle flows per billing type:
#   PIX:       CREATED → RECEIVED
#   BOLETO:    CREATED → CONFIRMED → RECEIVED
#   CREDIT_CARD: CREATED → CONFIRMED → RECEIVED (32 days after CONFIRMED)
#
# We map:
#   CONFIRMED → APROVADO (payment confirmed, funds pending)
#   RECEIVED  → APROVADO (funds available)
# Both are safe to unlock course access because the payment is confirmed.
# For PIX, RECEIVED is the only confirmation event (no CONFIRMED).
# For BOLETO/CREDIT_CARD, CONFIRMED means the payer paid — we unlock
# immediately rather than waiting for RECEIVED (which can take days).
_ASAAS_EVENT_MAP = {
    # Creation / updates — processing
    "PAYMENT_CREATED": PaymentStatus.PROCESSANDO,
    "PAYMENT_AWAITING_RISK_ANALYSIS": PaymentStatus.PROCESSANDO,
    "PAYMENT_APPROVED_BY_RISK_ANALYSIS": PaymentStatus.PROCESSANDO,
    "PAYMENT_REPROVED_BY_RISK_ANALYSIS": PaymentStatus.RECUSADO,
    "PAYMENT_AUTHORIZED": PaymentStatus.PROCESSANDO,
    "PAYMENT_UPDATED": PaymentStatus.PROCESSANDO,
    # Confirmation — funds confirmed (safe to unlock)
    "PAYMENT_CONFIRMED": PaymentStatus.APROVADO,
    "PAYMENT_RECEIVED": PaymentStatus.APROVADO,
    "PAYMENT_ANTICIPATED": PaymentStatus.APROVADO,
    # Overdue — still processing (may still be paid)
    "PAYMENT_OVERDUE": PaymentStatus.PROCESSANDO,
    # Refunds
    "PAYMENT_REFUNDED": PaymentStatus.REEMBOLSADO,
    "PAYMENT_PARTIALLY_REFUNDED": PaymentStatus.APROVADO,  # partial refund keeps approval
    "PAYMENT_REFUND_IN_PROGRESS": PaymentStatus.PROCESSANDO,
    "PAYMENT_REFUND_DENIED": PaymentStatus.APROVADO,  # refund denied = payment stands
    "PAYMENT_REFUND_REQUESTED": PaymentStatus.PROCESSANDO,
    # Chargebacks — refused/reversed
    "PAYMENT_CHARGEBACK_REQUESTED": PaymentStatus.RECUSADO,
    "PAYMENT_CHARGEBACK_DISPUTE": PaymentStatus.RECUSADO,
    "PAYMENT_AWAITING_CHARGEBACK_REVERSAL": PaymentStatus.RECUSADO,
    # Card capture refused
    "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED": PaymentStatus.RECUSADO,
    # Deleted / restored
    "PAYMENT_DELETED": PaymentStatus.RECUSADO,
    "PAYMENT_RESTORED": PaymentStatus.PROCESSANDO,
    # Cash undone — reverse the confirmation
    "PAYMENT_RECEIVED_IN_CASH_UNDONE": PaymentStatus.PROCESSANDO,
    # Bank slip cancelled — still processing (boleto expired, charge may be re-issued)
    "PAYMENT_BANK_SLIP_CANCELLED": PaymentStatus.PROCESSANDO,
    # Viewed events — informational only, no status change
    "PAYMENT_BANK_SLIP_VIEWED": None,
    "PAYMENT_CHECKOUT_VIEWED": None,
    # Split events — informational, no status change
    "PAYMENT_SPLIT_CANCELLED": None,
    "PAYMENT_SPLIT_DIVERGENCE_BLOCK": None,
    "PAYMENT_SPLIT_DIVERGENCE_BLOCK_FINISHED": None,
    "PAYMENT_SPLIT_DONE": None,
    # Dunning — informational
    "PAYMENT_DUNNING_RECEIVED": None,
    "PAYMENT_DUNNING_REQUESTED": None,
}

# Events that can transition a payment to APROVADO (require full identity verification).
_APPROVAL_EVENTS = frozenset({
    "PAYMENT_CONFIRMED",
    "PAYMENT_RECEIVED",
    "PAYMENT_ANTICIPATED",
})


def _constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    return hmac.compare_digest(a.encode(), b.encode())


def _generate_webhook_token() -> str:
    """Generate a cryptographically secure random webhook token.

    Must be 32-255 characters per Asaas requirements.
    token_urlsafe(32) produces ~43 characters.
    """
    return pysecrets.token_urlsafe(32)


async def _get_tenant_by_slug(db: AsyncSession, slug: str) -> Tenant | None:
    stmt = select(Tenant).where(Tenant.slug == slug)
    return (await db.execute(stmt)).scalar_one_or_none()


def _resolve_webhook_url(tenant_slug: str) -> str:
    """Resolve the production webhook callback URL.

    Uses ASAAS_WEBHOOK_BASE_URL from trusted backend configuration.
    Falls back to API_BASE_URL if ASAAS_WEBHOOK_BASE_URL is not set.
    """
    base = getattr(settings, "ASAAS_WEBHOOK_BASE_URL", "") or settings.API_BASE_URL
    base = base.rstrip("/")
    return f"{base}/api/v1/integrations/asaas/webhook/{tenant_slug}"


def _validate_production_key_format(api_key: str) -> None:
    """Validate the API key format for the current environment.

    Production keys must start with $aact_prod_.
    Sandbox keys start with $aact_hmlg_.
    In production, sandbox keys are rejected.
    """
    is_production = settings.ENVIRONMENT.lower() == "production"
    if is_production:
        if not api_key.startswith("$aact_prod_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Production API key must start with $aact_prod_",
            )
    # In non-production, accept either format or test keys
    elif not api_key.startswith("$aact_") and len(api_key) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key format",
        )


# ------------------------------------------------------------------
# Integration status and management
# ------------------------------------------------------------------

@router.get("/status")
async def asaas_status(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Returns the real Asaas integration status for the current tenant.

    Never reveals credentials. Reports real operational state:
    - configured: API key stored
    - connection_valid: API key validated successfully
    - webhook_configured: webhook actually exists in Asaas (not just token)
    - webhook_enabled: webhook is active in Asaas
    - webhook_interrupted: webhook queue is interrupted
    - webhook_id: Asaas webhook identifier
    - last_validation_at: last successful validation timestamp
    - last_webhook_at: last webhook reconciliation timestamp
    """
    tenant_id = get_current_tenant_id()
    api_key = await get_asaas_api_key(db, tenant_id)
    webhook_token = await get_tenant_secret(db, tenant_id, ASAAS_WEBHOOK_TOKEN_KEY)

    tenant = await db.get(Tenant, tenant_id)
    tenant_settings = (tenant.settings if tenant else None) or {}
    configured_provider = (tenant_settings.get("payment_provider") or "").upper()

    # Read webhook metadata from tenant settings (stored during connect/reconcile)
    webhook_id = tenant_settings.get("asaas_webhook_id")
    webhook_enabled = tenant_settings.get("asaas_webhook_enabled", False)
    webhook_interrupted = tenant_settings.get("asaas_webhook_interrupted", True)
    last_validation_at = tenant_settings.get("asaas_last_validation_at")
    last_webhook_at = tenant_settings.get("asaas_last_webhook_reconciliation_at")

    # webhook_configured means the webhook ACTUALLY exists in Asaas,
    # not merely that a token exists locally.
    webhook_configured = bool(webhook_id) and bool(webhook_token)

    return {
        "configured": api_key is not None,
        "connection_valid": last_validation_at is not None,
        "webhook_configured": webhook_configured,
        "webhook_enabled": webhook_enabled,
        "webhook_interrupted": webhook_interrupted,
        "webhook_id": webhook_id,
        "active_provider": configured_provider or "MERCADO_PAGO",
        "is_asaas_active": configured_provider == "ASAAS",
        "last_validation_at": last_validation_at,
        "last_webhook_at": last_webhook_at,
    }


@router.post("/connect")
async def asaas_connect(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Connect Asaas by storing the production API key and reconciling webhook.

    All steps must succeed before returning "connected":
    1. Validate production key format.
    2. Read-only authentication request to Asaas.
    3. Store API key encrypted.
    4. Generate and store webhook token (NOT the API key).
    5. Resolve production callback URL from trusted config.
    6. Reconcile/create Asaas webhook via API.
    7. Verify webhook exists, URL matches, authToken matches, events configured.
    8. Verify webhook is enabled and not interrupted.
    9. Store webhook metadata in tenant settings.
    10. Mark provider as ASAAS.
    """
    tenant_id = get_current_tenant_id()
    body = await request.json()
    api_key = body.get("api_key", "").strip()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is required",
        )

    # ── Step 1: Validate key format ──
    _validate_production_key_format(api_key)

    # ── Load tenant ──
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant_settings = dict(tenant.settings or {})

    # ── Step 2: Read-only authentication validation ──
    is_mock = getattr(settings, "ASAAS_MOCK_MODE", False)
    if not is_mock:
        provider = AsaasProvider(api_key=api_key, sandbox=False)
        try:
            await provider._request("GET", "/v3/customers", params={"limit": 1})
        except PaymentProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Asaas API key validation failed",
            ) from exc

    # ── Step 3: Store API key encrypted ──
    await set_tenant_secret(db, tenant_id, ASAAS_API_KEY_KEY, api_key, "Asaas API key")

    # ── Step 4: Generate and store webhook token ──
    webhook_token = _generate_webhook_token()
    await set_tenant_secret(
        db, tenant_id, ASAAS_WEBHOOK_TOKEN_KEY, webhook_token, "Asaas webhook auth token"
    )

    # ── Step 5: Resolve production callback URL ──
    webhook_url = _resolve_webhook_url(tenant.slug)
    webhook_name = f"WR Cursos Payments - {tenant.slug}"

    # ── Steps 6-8: Reconcile/create Asaas webhook ──
    if not is_mock:
        provider = AsaasProvider(api_key=api_key, sandbox=False)
        try:
            wh_config = await provider.reconcile_webhook(
                webhook_name=webhook_name,
                webhook_url=webhook_url,
                auth_token=webhook_token,
                email=tenant.contact_email,
            )
        except PaymentProviderError as exc:
            # Don't persist provider setting if webhook failed
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to reconcile Asaas webhook",
            ) from exc

        # Verify webhook is healthy
        if not wh_config.enabled:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Asaas webhook is not enabled",
            )
        if wh_config.interrupted:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Asaas webhook queue is interrupted",
            )

        # Store webhook metadata
        tenant_settings["asaas_webhook_id"] = wh_config.id
        tenant_settings["asaas_webhook_enabled"] = wh_config.enabled
        tenant_settings["asaas_webhook_interrupted"] = wh_config.interrupted
        tenant_settings["asaas_last_webhook_reconciliation_at"] = utc_now().isoformat()
    else:
        # Mock mode: store mock webhook metadata
        tenant_settings["asaas_webhook_id"] = f"mock-wh-{tenant.slug}"
        tenant_settings["asaas_webhook_enabled"] = True
        tenant_settings["asaas_webhook_interrupted"] = False
        tenant_settings["asaas_last_webhook_reconciliation_at"] = utc_now().isoformat()

    # ── Step 9: Mark validation timestamp ──
    tenant_settings["asaas_last_validation_at"] = utc_now().isoformat()

    # ── Step 10: Mark provider as ASAAS ──
    tenant_settings["payment_provider"] = "ASAAS"
    tenant.settings = tenant_settings

    await db.commit()

    return {
        "status": "connected",
        "webhook_configured": True,
        "webhook_id": tenant_settings.get("asaas_webhook_id"),
        "message": "Asaas connected and webhook reconciled successfully.",
    }


@router.post("/validate")
async def asaas_validate(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Validate the stored Asaas connection with a read-only request.

    Also re-checks the webhook health.
    """
    tenant_id = get_current_tenant_id()
    api_key = await get_asaas_api_key(db, tenant_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asaas not configured",
        )

    is_mock = getattr(settings, "ASAAS_MOCK_MODE", False)
    if is_mock:
        return {"valid": True, "message": "Mock mode — validation skipped", "webhook_healthy": True}

    provider = AsaasProvider(api_key=api_key, sandbox=False)
    try:
        await provider._request("GET", "/v3/customers", params={"limit": 1})
    except PaymentProviderError:
        return {"valid": False, "message": "Validation failed", "webhook_healthy": False}

    # Update validation timestamp
    tenant = await db.get(Tenant, tenant_id)
    if tenant:
        ts = dict(tenant.settings or {})
        ts["asaas_last_validation_at"] = utc_now().isoformat()
        tenant.settings = ts
        await db.commit()

    # Check webhook health
    webhook_id = (tenant.settings if tenant else {}).get("asaas_webhook_id")
    webhook_healthy = False
    if webhook_id:
        try:
            wh = await provider.get_webhook(webhook_id)
            webhook_healthy = wh is not None and wh.enabled and not wh.interrupted
        except PaymentProviderError:
            webhook_healthy = False

    return {"valid": True, "message": "Connection is valid", "webhook_healthy": webhook_healthy}


@router.delete("/")
async def asaas_disconnect(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    """Disconnect Asaas by removing stored credentials and disabling webhook.

    Also disables/deletes the remote webhook so Asaas does not continue
    sending events to a disconnected tenant.
    """
    from app.models.tenant_secret import TenantSecret

    tenant_id = get_current_tenant_id()
    tenant = await db.get(Tenant, tenant_id)
    tenant_settings = dict(tenant.settings or {}) if tenant else {}

    # ── Disable/delete remote webhook ──
    webhook_id = tenant_settings.get("asaas_webhook_id")
    api_key = await get_asaas_api_key(db, tenant_id)
    is_mock = getattr(settings, "ASAAS_MOCK_MODE", False)

    if webhook_id and api_key and not is_mock:
        provider = AsaasProvider(api_key=api_key, sandbox=False)
        try:
            # Disable the webhook first (safer than delete — can be re-enabled)
            await provider.update_webhook(webhook_id=webhook_id, enabled=False)
        except PaymentProviderError:
            logger.warning("Failed to disable Asaas webhook %s during disconnect", webhook_id)

    # ── Remove API key ──
    stmt = select(TenantSecret).where(
        TenantSecret.tenant_id == tenant_id,
        TenantSecret.key == ASAAS_API_KEY_KEY,
    )
    secret = (await db.execute(stmt)).scalar_one_or_none()
    if secret:
        await db.delete(secret)

    # ── Remove webhook token ──
    stmt = select(TenantSecret).where(
        TenantSecret.tenant_id == tenant_id,
        TenantSecret.key == ASAAS_WEBHOOK_TOKEN_KEY,
    )
    secret = (await db.execute(stmt)).scalar_one_or_none()
    if secret:
        await db.delete(secret)

    # ── Revert tenant settings ──
    if tenant:
        tenant_settings.pop("payment_provider", None)
        tenant_settings.pop("asaas_webhook_id", None)
        tenant_settings.pop("asaas_webhook_enabled", None)
        tenant_settings.pop("asaas_webhook_interrupted", None)
        tenant_settings.pop("asaas_last_validation_at", None)
        tenant_settings.pop("asaas_last_webhook_reconciliation_at", None)
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

    Idempotency with state machine:
    - PaymentWebhookEvent ledger with unique constraint on
      (tenant, provider, provider_event_id).
    - Event states: RECEIVED → PENDING_MATCH → PROCESSED | IGNORED | FAILED
    - Only PROCESSED (terminal success) prevents future reconciliation.
    - PENDING_MATCH allows retry (payment may not exist yet).
    - Concurrent duplicate requests: catch IntegrityError, return 2xx.

    Payment identity verification (for approval-capable events):
    - Resolved tenant must match payment's tenant.
    - provider == ASAAS.
    - provider_payment_id must match.
    - externalReference must match str(internal Payment.id).
    - Amount must match Payment.amount.
    - Provider customer association verified via GET /v3/payments/{id}.
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

    # ── Idempotency: check if event already terminally processed ──
    existing_event = (
        await db.execute(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.tenant_id == tenant.id,
                PaymentWebhookEvent.provider == PaymentProvider.ASAAS,
                PaymentWebhookEvent.provider_event_id == event_id,
            )
        )
    ).scalar_one_or_none()

    if existing_event and _is_terminal_state(existing_event.result):
        # Duplicate of a terminally processed event — acknowledge without re-processing
        return {"status": "ok", "duplicate": True, "state": existing_event.result}

    # ── Insert event record (handle race condition via IntegrityError) ──
    if not existing_event:
        event_record = PaymentWebhookEvent(
            tenant_id=tenant.id,
            provider=PaymentProvider.ASAAS,
            provider_event_id=event_id,
            event_type=event_type,
            provider_payment_id=provider_payment_id,
            result=EVENT_STATE_RECEIVED,
        )
        db.add(event_record)
        try:
            await db.flush()
        except IntegrityError:
            # Concurrent duplicate request won the race — acknowledge
            await db.rollback()
            return {"status": "ok", "duplicate": True, "state": "concurrent_duplicate"}
    else:
        # Event exists but is not terminal (PENDING_MATCH, RECEIVED, FAILED) — reprocess
        event_record = existing_event
        event_record.result = EVENT_STATE_RECEIVED

    # ── Find the internal payment by provider_payment_id ──
    # Never trust tenant_id from the payload — use the resolved tenant.
    stmt = select(Payment).where(
        Payment.tenant_id == tenant.id,
        Payment.provider == PaymentProvider.ASAAS,
        Payment.provider_payment_id == provider_payment_id,
    )
    payment = (await db.execute(stmt)).scalar_one_or_none()

    if not payment:
        # Payment not found — set to PENDING_MATCH (NOT terminal)
        # This allows future retry/reconciliation when the payment is created.
        event_record.result = EVENT_STATE_PENDING_MATCH
        await db.commit()
        return {"status": "ok", "payment_found": False, "state": EVENT_STATE_PENDING_MATCH}

    # ── Map event to internal status ──
    new_status = _ASAAS_EVENT_MAP.get(event_type)

    if new_status is None:
        # Unknown or informational event — record as IGNORED (terminal, safe)
        event_record.result = f"{EVENT_STATE_IGNORED}:{event_type}"
        await db.commit()
        return {"status": "ok", "unknown_event": True, "state": EVENT_STATE_IGNORED}

    # ── Payment identity verification ──
    # For approval-capable events, retrieve canonical state from Asaas
    # and verify externalReference, amount, and customer.
    is_approval_event = event_type in _APPROVAL_EVENTS

    if is_approval_event:
        verification_result = await _verify_payment_identity(
            db, tenant, payment, provider_payment_id, event_type
        )
        if not verification_result["valid"]:
            # Identity mismatch — do NOT confirm enrollment
            event_record.result = f"{EVENT_STATE_FAILED}:{verification_result['reason']}"
            await db.commit()
            logger.warning(
                "Webhook identity verification failed for payment %s: %s",
                payment.id,
                verification_result["reason"],
            )
            return {
                "status": "ok",
                "verification_failed": True,
                "reason": verification_result["reason"],
                "state": EVENT_STATE_FAILED,
            }

    # ── Load enrollment for reconciliation ──
    enrollment = None
    if payment.enrollment_id:
        enrollment = await db.get(Enrollment, payment.enrollment_id)
        if not enrollment or enrollment.tenant_id != tenant.id:
            event_record.result = f"{EVENT_STATE_FAILED}:enrollment_tenant_mismatch"
            await db.commit()
            return {
                "status": "ok",
                "error": "enrollment_tenant_mismatch",
                "state": EVENT_STATE_FAILED,
            }

    # ── Apply status transition via shared reconciliation ──
    if enrollment:
        result = await reconcile_payment_status(payment, enrollment, new_status)
        event_record.result = f"{EVENT_STATE_PROCESSED}:{json.dumps(result)}"
    else:
        # Company payment (no enrollment) — just update payment status
        if payment.status != new_status:
            payment.status = new_status
            if new_status == PaymentStatus.APROVADO:
                payment.paid_at = utc_now()
        event_record.result = EVENT_STATE_PROCESSED

    await db.commit()

    return {
        "status": "ok",
        "event": event_type,
        "payment_status": new_status.value,
        "state": EVENT_STATE_PROCESSED,
    }


async def _verify_payment_identity(
    db: AsyncSession,
    tenant: Tenant,
    payment: Payment,
    provider_payment_id: str,
    event_type: str,
) -> dict:
    """Verify payment identity by retrieving canonical state from Asaas.

    Uses GET /v3/payments/{provider_payment_id} with the resolved tenant's
    API key to verify:
    - externalReference == str(payment.id)
    - value == payment.amount
    - customer matches the PaymentCustomer mapping (if available)
    - billingType/status is consistent with the event

    Returns {"valid": bool, "reason": str}.
    """
    is_mock = getattr(settings, "ASAAS_MOCK_MODE", False)

    # In mock mode, skip provider retrieval — there's no real Asaas to verify against.
    # The mock provider returns deterministic fake data that won't match real payment UUIDs.
    # Mock mode is only for testing the webhook flow, not identity verification.
    if is_mock:
        return {"valid": True, "reason": "ok_mock"}

    api_key = await get_asaas_api_key(db, tenant.id)
    if not api_key:
        return {"valid": False, "reason": "no_api_key"}

    provider = AsaasProvider(api_key=api_key, sandbox=False, mock=False)

    try:
        info = await provider.get_payment_info(provider_payment_id)
    except PaymentProviderError:
        return {"valid": False, "reason": "provider_retrieval_failed"}

    # 1. externalReference must match str(payment.id)
    if info.external_reference != str(payment.id):
        return {"valid": False, "reason": "external_reference_mismatch"}

    # 2. Amount must match
    if info.amount is not None and abs(float(info.amount) - float(payment.amount)) > 0.01:
        return {"valid": False, "reason": "amount_mismatch"}

    # 3. Provider customer association (if we have a mapping)
    from app.models.payment import PaymentCustomer
    if payment.enrollment_id:
        # Student payment — check customer mapping
        from sqlalchemy import select as sel
        # Find the student for this enrollment
        enrollment = await db.get(Enrollment, payment.enrollment_id)
        if enrollment:
            cust_stmt = sel(PaymentCustomer).where(
                PaymentCustomer.tenant_id == tenant.id,
                PaymentCustomer.student_id == enrollment.student_id,
                PaymentCustomer.provider == PaymentProvider.ASAAS,
            )
            customer_mapping = (await db.execute(cust_stmt)).scalar_one_or_none()
            if customer_mapping and info.customer_id and customer_mapping.provider_customer_id != info.customer_id:
                return {"valid": False, "reason": "customer_mismatch"}

    # 4. For CONFIRMED events on PIX, verify status is actually CONFIRMED or RECEIVED
    # (PIX goes directly to RECEIVED — a synthetic CONFIRMED would be suspicious)
    if event_type == "PAYMENT_CONFIRMED" and info.billing_type == "PIX" and info.status not in ("CONFIRMED", "RECEIVED"):
        return {"valid": False, "reason": "pix_status_inconsistent"}

    return {"valid": True, "reason": "ok"}
