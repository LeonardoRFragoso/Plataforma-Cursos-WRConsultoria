"""Asaas integration management routes.

Provides admin-facing endpoints for connecting, validating, and
disconnecting the Asaas payment provider for a tenant. Also provides
the authenticated webhook endpoint for receiving Asaas payment events.

All financial credentials are write-only: they can be configured,
replaced, deleted, and validated, but never revealed in plaintext.
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
from app.services.financial_lifecycle import (
    SPECIAL_FINANCIAL_EVENTS,
    reconcile_special_financial_event,
)
from app.services.payment_provider_base import PaymentProviderError
from app.services.payment_reconciliation import reconcile_payment_status
from app.services.tenant_secret_service import (
    ASAAS_API_KEY_KEY,
    get_asaas_api_key,
    get_tenant_secret,
    set_tenant_secret,
)
from app.services.transactional_notifications import send_course_access_notification

logger = logging.getLogger(__name__)

router = APIRouter()

ASAAS_WEBHOOK_TOKEN_KEY = "asaas_webhook_token"

EVENT_STATE_RECEIVED = "RECEIVED"
EVENT_STATE_PENDING_MATCH = "PENDING_MATCH"
EVENT_STATE_PROCESSED = "PROCESSED"
EVENT_STATE_IGNORED = "IGNORED"
EVENT_STATE_FAILED = "FAILED"

_TERMINAL_STATE_PREFIXES = (
    EVENT_STATE_PROCESSED,
    EVENT_STATE_IGNORED,
)


def _is_terminal_state(result: str) -> bool:
    """Check if an event result is terminal (prevents future reconciliation)."""
    return any(
        result == prefix or result.startswith(f"{prefix}:")
        for prefix in _TERMINAL_STATE_PREFIXES
    )


_ASAAS_EVENT_MAP = {
    "PAYMENT_CREATED": PaymentStatus.PROCESSANDO,
    "PAYMENT_AWAITING_RISK_ANALYSIS": PaymentStatus.PROCESSANDO,
    "PAYMENT_APPROVED_BY_RISK_ANALYSIS": PaymentStatus.PROCESSANDO,
    "PAYMENT_REPROVED_BY_RISK_ANALYSIS": PaymentStatus.RECUSADO,
    "PAYMENT_AUTHORIZED": PaymentStatus.PROCESSANDO,
    "PAYMENT_UPDATED": PaymentStatus.PROCESSANDO,
    "PAYMENT_CONFIRMED": PaymentStatus.APROVADO,
    "PAYMENT_RECEIVED": PaymentStatus.APROVADO,
    "PAYMENT_ANTICIPATED": PaymentStatus.APROVADO,
    # OVERDUE is not expiration: Asaas can still receive boleto/PIX after due
    # date, so the external charge remains active until a terminal event.
    "PAYMENT_OVERDUE": PaymentStatus.PROCESSANDO,
    # Special financial events are reconciled by financial_lifecycle.py.
    "PAYMENT_REFUNDED": None,
    "PAYMENT_PARTIALLY_REFUNDED": None,
    "PAYMENT_REFUND_IN_PROGRESS": None,
    "PAYMENT_REFUND_DENIED": None,
    "PAYMENT_REFUND_REQUESTED": PaymentStatus.PROCESSANDO,
    "PAYMENT_CHARGEBACK_REQUESTED": None,
    "PAYMENT_CHARGEBACK_DISPUTE": None,
    "PAYMENT_AWAITING_CHARGEBACK_REVERSAL": None,
    "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED": PaymentStatus.RECUSADO,
    "PAYMENT_DELETED": PaymentStatus.RECUSADO,
    "PAYMENT_RESTORED": PaymentStatus.PROCESSANDO,
    "PAYMENT_RECEIVED_IN_CASH_UNDONE": PaymentStatus.PROCESSANDO,
    "PAYMENT_BANK_SLIP_CANCELLED": None,
    "PAYMENT_BANK_SLIP_VIEWED": None,
    "PAYMENT_CHECKOUT_VIEWED": None,
    "PAYMENT_SPLIT_CANCELLED": None,
    "PAYMENT_SPLIT_DIVERGENCE_BLOCK": None,
    "PAYMENT_SPLIT_DIVERGENCE_BLOCK_FINISHED": None,
    "PAYMENT_SPLIT_DONE": None,
    "PAYMENT_DUNNING_RECEIVED": None,
    "PAYMENT_DUNNING_REQUESTED": None,
}

_APPROVAL_EVENTS = frozenset(
    {
        "PAYMENT_CONFIRMED",
        "PAYMENT_RECEIVED",
        "PAYMENT_ANTICIPATED",
    }
)


def _constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _generate_webhook_token() -> str:
    return pysecrets.token_urlsafe(32)


async def _get_tenant_by_slug(db: AsyncSession, slug: str) -> Tenant | None:
    stmt = select(Tenant).where(Tenant.slug == slug)
    return (await db.execute(stmt)).scalar_one_or_none()


def _resolve_webhook_url(tenant_slug: str) -> str:
    base = getattr(settings, "ASAAS_WEBHOOK_BASE_URL", "") or settings.API_BASE_URL
    base = base.rstrip("/")
    return f"{base}/api/v1/integrations/asaas/webhook/{tenant_slug}"


def _validate_production_key_format(api_key: str) -> None:
    is_production = settings.ENVIRONMENT.lower() == "production"
    if is_production:
        if not api_key.startswith("$aact_prod_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Production API key must start with $aact_prod_",
            )
    elif not api_key.startswith("$aact_") and len(api_key) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API key format",
        )


@router.get("/status")
async def asaas_status(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    tenant_id = get_current_tenant_id()
    api_key = await get_asaas_api_key(db, tenant_id)
    webhook_token = await get_tenant_secret(db, tenant_id, ASAAS_WEBHOOK_TOKEN_KEY)

    tenant = await db.get(Tenant, tenant_id)
    tenant_settings = (tenant.settings if tenant else None) or {}
    configured_provider = (tenant_settings.get("payment_provider") or "").upper()

    webhook_id = tenant_settings.get("asaas_webhook_id")
    webhook_enabled = tenant_settings.get("asaas_webhook_enabled", False)
    webhook_interrupted = tenant_settings.get("asaas_webhook_interrupted", True)
    last_validation_at = tenant_settings.get("asaas_last_validation_at")
    last_webhook_at = tenant_settings.get("asaas_last_webhook_reconciliation_at")
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
    tenant_id = get_current_tenant_id()
    body = await request.json()
    api_key = body.get("api_key", "").strip()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is required",
        )

    _validate_production_key_format(api_key)

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant_settings = dict(tenant.settings or {})

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

    await set_tenant_secret(
        db,
        tenant_id,
        ASAAS_API_KEY_KEY,
        api_key,
        "Asaas API key",
    )

    webhook_token = _generate_webhook_token()
    await set_tenant_secret(
        db,
        tenant_id,
        ASAAS_WEBHOOK_TOKEN_KEY,
        webhook_token,
        "Asaas webhook auth token",
    )

    webhook_url = _resolve_webhook_url(tenant.slug)
    webhook_name = f"WR Cursos Payments - {tenant.slug}"

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
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to reconcile Asaas webhook",
            ) from exc

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

        tenant_settings["asaas_webhook_id"] = wh_config.id
        tenant_settings["asaas_webhook_enabled"] = wh_config.enabled
        tenant_settings["asaas_webhook_interrupted"] = wh_config.interrupted
        tenant_settings["asaas_last_webhook_reconciliation_at"] = utc_now().isoformat()
    else:
        tenant_settings["asaas_webhook_id"] = f"mock-wh-{tenant.slug}"
        tenant_settings["asaas_webhook_enabled"] = True
        tenant_settings["asaas_webhook_interrupted"] = False
        tenant_settings["asaas_last_webhook_reconciliation_at"] = utc_now().isoformat()

    tenant_settings["asaas_last_validation_at"] = utc_now().isoformat()
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
    tenant_id = get_current_tenant_id()
    api_key = await get_asaas_api_key(db, tenant_id)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asaas not configured",
        )

    is_mock = getattr(settings, "ASAAS_MOCK_MODE", False)
    if is_mock:
        return {
            "valid": True,
            "message": "Mock mode — validation skipped",
            "webhook_healthy": True,
        }

    provider = AsaasProvider(api_key=api_key, sandbox=False)
    try:
        await provider._request("GET", "/v3/customers", params={"limit": 1})
    except PaymentProviderError:
        return {
            "valid": False,
            "message": "Validation failed",
            "webhook_healthy": False,
        }

    tenant = await db.get(Tenant, tenant_id)
    if tenant:
        ts = dict(tenant.settings or {})
        ts["asaas_last_validation_at"] = utc_now().isoformat()
        tenant.settings = ts
        await db.commit()

    webhook_id = (tenant.settings if tenant else {}).get("asaas_webhook_id")
    webhook_healthy = False
    if webhook_id:
        try:
            wh = await provider.get_webhook(webhook_id)
            webhook_healthy = wh is not None and wh.enabled and not wh.interrupted
        except PaymentProviderError:
            webhook_healthy = False

    return {
        "valid": True,
        "message": "Connection is valid",
        "webhook_healthy": webhook_healthy,
    }


@router.delete("/")
async def asaas_disconnect(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    from app.models.tenant_secret import TenantSecret

    tenant_id = get_current_tenant_id()
    tenant = await db.get(Tenant, tenant_id)
    tenant_settings = dict(tenant.settings or {}) if tenant else {}

    webhook_id = tenant_settings.get("asaas_webhook_id")
    api_key = await get_asaas_api_key(db, tenant_id)
    is_mock = getattr(settings, "ASAAS_MOCK_MODE", False)

    if webhook_id and api_key and not is_mock:
        provider = AsaasProvider(api_key=api_key, sandbox=False)
        try:
            await provider.update_webhook(webhook_id=webhook_id, enabled=False)
        except PaymentProviderError:
            logger.warning(
                "Failed to disable Asaas webhook %s during disconnect",
                webhook_id,
            )

    stmt = select(TenantSecret).where(
        TenantSecret.tenant_id == tenant_id,
        TenantSecret.key == ASAAS_API_KEY_KEY,
    )
    secret = (await db.execute(stmt)).scalar_one_or_none()
    if secret:
        await db.delete(secret)

    stmt = select(TenantSecret).where(
        TenantSecret.tenant_id == tenant_id,
        TenantSecret.key == ASAAS_WEBHOOK_TOKEN_KEY,
    )
    secret = (await db.execute(stmt)).scalar_one_or_none()
    if secret:
        await db.delete(secret)

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


@router.post("/webhook/{tenant_slug}")
async def asaas_webhook(
    tenant_slug: str,
    request: Request,
    asaas_access_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Authenticated, tenant-scoped and idempotent Asaas payment webhook."""
    tenant = await _get_tenant_by_slug(db, tenant_slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    webhook_token = await get_tenant_secret(db, tenant.id, ASAAS_WEBHOOK_TOKEN_KEY)
    if not webhook_token:
        raise HTTPException(status_code=403, detail="Webhook not configured")
    if not asaas_access_token:
        raise HTTPException(status_code=403, detail="Missing access token")
    if not _constant_time_compare(asaas_access_token, webhook_token):
        raise HTTPException(status_code=403, detail="Invalid access token")

    body = await request.json()
    event_id = body.get("id", "")
    event_type = body.get("event", "")
    payment_obj = body.get("payment", {})
    if isinstance(payment_obj, dict):
        provider_payment_id = payment_obj.get("id", "")
    else:
        provider_payment_id = str(payment_obj)

    if not event_id or not provider_payment_id:
        raise HTTPException(
            status_code=400,
            detail="Missing event id or payment id",
        )

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
        return {
            "status": "ok",
            "duplicate": True,
            "state": existing_event.result,
        }

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
            await db.rollback()
            return {
                "status": "ok",
                "duplicate": True,
                "state": "concurrent_duplicate",
            }
    else:
        event_record = existing_event
        event_record.result = EVENT_STATE_RECEIVED

    stmt = select(Payment).where(
        Payment.tenant_id == tenant.id,
        Payment.provider == PaymentProvider.ASAAS,
        Payment.provider_payment_id == provider_payment_id,
    )
    payment = (await db.execute(stmt)).scalar_one_or_none()

    if not payment:
        event_record.result = EVENT_STATE_PENDING_MATCH
        await db.commit()
        return {
            "status": "ok",
            "payment_found": False,
            "state": EVENT_STATE_PENDING_MATCH,
        }

    is_special_financial_event = event_type in SPECIAL_FINANCIAL_EVENTS
    new_status = _ASAAS_EVENT_MAP.get(event_type)
    if new_status is None and not is_special_financial_event:
        event_record.result = f"{EVENT_STATE_IGNORED}:{event_type}"
        await db.commit()
        return {
            "status": "ok",
            "unknown_event": True,
            "state": EVENT_STATE_IGNORED,
        }

    if event_type in _APPROVAL_EVENTS:
        verification_result = await _verify_payment_identity(
            db,
            tenant,
            payment,
            provider_payment_id,
            event_type,
        )
        if not verification_result["valid"]:
            event_record.result = (
                f"{EVENT_STATE_FAILED}:{verification_result['reason']}"
            )
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

    enrollment = None
    if payment.enrollment_id:
        enrollment = await db.get(Enrollment, payment.enrollment_id)
        if not enrollment or enrollment.tenant_id != tenant.id:
            event_record.result = (
                f"{EVENT_STATE_FAILED}:enrollment_tenant_mismatch"
            )
            await db.commit()
            return {
                "status": "ok",
                "error": "enrollment_tenant_mismatch",
                "state": EVENT_STATE_FAILED,
            }

    should_notify_course_access = False
    if is_special_financial_event:
        result = await reconcile_special_financial_event(
            db,
            payment,
            enrollment,
            event_type,
        )
        event_record.result = f"{EVENT_STATE_PROCESSED}:{json.dumps(result)}"
    elif enrollment:
        result = await reconcile_payment_status(payment, enrollment, new_status)
        should_notify_course_access = bool(
            result.get("enrollment_newly_confirmed")
        )
        event_record.result = (
            f"{EVENT_STATE_PROCESSED}:{json.dumps(result)}"
        )
    else:
        if payment.status != new_status:
            payment.status = new_status
            if new_status == PaymentStatus.APROVADO:
                payment.paid_at = utc_now()
        event_record.result = EVENT_STATE_PROCESSED

    # Financial/enrollment state commits first. Email is a best-effort side
    # effect and can never roll back the confirmed purchase.
    await db.commit()

    if should_notify_course_access and enrollment:
        await send_course_access_notification(db, enrollment)

    return {
        "status": "ok",
        "event": event_type,
        "payment_status": payment.status.value,
        "review_required": bool(payment.review_required),
        "state": EVENT_STATE_PROCESSED,
    }


async def _verify_payment_identity(
    db: AsyncSession,
    tenant: Tenant,
    payment: Payment,
    provider_payment_id: str,
    event_type: str,
) -> dict:
    """Verify canonical Asaas payment identity before an approval transition."""
    is_mock = getattr(settings, "ASAAS_MOCK_MODE", False)
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

    if info.external_reference != str(payment.id):
        return {"valid": False, "reason": "external_reference_mismatch"}

    if (
        info.amount is not None
        and abs(float(info.amount) - float(payment.amount)) > 0.01
    ):
        return {"valid": False, "reason": "amount_mismatch"}

    from app.models.payment import PaymentCustomer

    if payment.enrollment_id:
        enrollment = await db.get(Enrollment, payment.enrollment_id)
        if enrollment:
            cust_stmt = select(PaymentCustomer).where(
                PaymentCustomer.tenant_id == tenant.id,
                PaymentCustomer.student_id == enrollment.student_id,
                PaymentCustomer.provider == PaymentProvider.ASAAS,
            )
            customer_mapping = (
                await db.execute(cust_stmt)
            ).scalar_one_or_none()
            if (
                customer_mapping
                and info.customer_id
                and customer_mapping.provider_customer_id != info.customer_id
            ):
                return {"valid": False, "reason": "customer_mismatch"}

    if (
        event_type == "PAYMENT_CONFIRMED"
        and info.billing_type == "PIX"
        and info.status not in ("CONFIRMED", "RECEIVED")
    ):
        return {"valid": False, "reason": "pix_status_inconsistent"}

    return {"valid": True, "reason": "ok"}
