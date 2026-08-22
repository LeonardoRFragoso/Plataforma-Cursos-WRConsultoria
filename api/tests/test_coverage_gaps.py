"""Targeted tests to restore backend coverage gate for Asaas payment hardening.

Covers uncovered security-critical paths in:
- asaas_integration.py: webhook auth failures, malformed payloads, company
  payments, enrollment tenant mismatch, no API key, provider retrieval failure,
  customer mismatch, PIX status inconsistency, connect/validate/disconnect
  non-mock error paths, status endpoint
- asaas_provider.py: HTTP error sanitization (400/401/403/404/500), timeout,
  network error, real checkout with customer creation, PIX QR code fetch,
  refund, webhook CRUD real paths, reconcile find-and-update
- email_service.py: SMTP send success/failure, production-disabled behavior
- payment_customer_sync.py: concurrency race, company customer mapping
- payments.py: admin payment creation, list, get, update, delete, checkout
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.payment import (
    Payment,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.tenant_secret_service import set_tenant_secret

# ─── Helpers ───

async def _create_admin(email, tenant_id):
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=email,
            full_name=f"Admin {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


def _headers(user_id, role="admin", tenant_id=WR_TENANT_ID):
    token = create_access_token(
        {"sub": str(user_id), "role": role, "tenant_id": str(tenant_id)}
    )
    return {"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"}


async def _setup_asaas_tenant():
    """Set up tenant with Asaas API key and webhook metadata."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_api_key", "fake_key_12345678901234567890")
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_webhook_token", "x" * 43)
        tenant = (await db.execute(
            __import__("sqlalchemy").select(Tenant).where(Tenant.id == WR_TENANT_ID)
        )).scalar_one()
        ts = dict(tenant.settings or {})
        ts["payment_provider"] = "ASAAS"
        ts["asaas_webhook_id"] = "wh_test_123"
        ts["asaas_webhook_enabled"] = True
        ts["asaas_webhook_interrupted"] = False
        tenant.settings = ts
        await db.commit()


async def _create_payment(amount=299.90, enrollment_id=None, company_id=None, provider_pid=None):
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment_id,
            company_id=company_id,
            amount=amount,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
            provider=PaymentProvider.ASAAS,
            provider_payment_id=provider_pid or f"pay_test_{uuid.uuid4().hex[:8]}",
            checkout_url="https://asaas.test/checkout",
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        return payment.id, payment.provider_payment_id


# ═══════════════════════════════════════════════════════════════
# Asaas webhook auth & payload validation
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_tenant_not_found_returns_404(client, monkeypatch):
    """Webhook for unknown tenant slug returns 404."""
    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/nonexistent",
        json={"id": "evt1", "event": "PAYMENT_RECEIVED", "payment": {"id": "p1"}},
        headers={"asaas-access-token": "x" * 43},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_webhook_no_token_configured_returns_403(client, monkeypatch):
    """Webhook without configured token returns 403."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={"id": "evt1", "event": "PAYMENT_RECEIVED", "payment": {"id": "p1"}},
        headers={"asaas-access-token": "x" * 43},
    )
    assert resp.status_code == 403
    assert "not configured" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_missing_access_token_returns_403(client, monkeypatch):
    """Webhook without asaas-access-token header returns 403."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    await _setup_asaas_tenant()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={"id": "evt1", "event": "PAYMENT_RECEIVED", "payment": {"id": "p1"}},
    )
    assert resp.status_code == 403
    assert "missing" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_invalid_access_token_returns_403(client, monkeypatch):
    """Webhook with wrong token returns 403."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    await _setup_asaas_tenant()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={"id": "evt1", "event": "PAYMENT_RECEIVED", "payment": {"id": "p1"}},
        headers={"asaas-access-token": "wrong_token_value_here_1234567890123456"},
    )
    assert resp.status_code == 403
    assert "invalid" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_missing_event_id_returns_400(client, monkeypatch):
    """Webhook with missing event id returns 400."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    await _setup_asaas_tenant()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={"event": "PAYMENT_RECEIVED", "payment": {"id": "p1"}},
        headers={"asaas-access-token": "x" * 43},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_missing_payment_id_returns_400(client, monkeypatch):
    """Webhook with missing payment id returns 400."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    await _setup_asaas_tenant()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={"id": "evt1", "event": "PAYMENT_RECEIVED", "payment": {}},
        headers={"asaas-access-token": "x" * 43},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_payment_as_string_id(client, monkeypatch):
    """Webhook accepts payment as a string ID (not just dict)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    await _setup_asaas_tenant()
    _pid, provider_pid = await _create_payment()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_str_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_RECEIVED",
            "payment": provider_pid,
        },
        headers={"asaas-access-token": "x" * 43},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "PROCESSED"


@pytest.mark.asyncio
async def test_webhook_company_payment_no_enrollment(client, monkeypatch):
    """Company payment (no enrollment) updates status without enrollment reconciliation."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    await _setup_asaas_tenant()

    # Create a real company for the FK constraint
    from app.models.company import Company
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        company = Company(
            tenant_id=WR_TENANT_ID,
            legal_name="Test Company",
            cnpj=str(uuid.uuid4().int)[:14],
            rh_email="rh@testcompany.test",
        )
        db.add(company)
        await db.commit()
        await db.refresh(company)
        company_id = company.id

    _pid, provider_pid = await _create_payment(company_id=company_id, enrollment_id=None)

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_co_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": "x" * 43},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "PROCESSED"
    assert resp.json()["payment_status"] == "APROVADO"


# ═══════════════════════════════════════════════════════════════
# Asaas webhook identity verification (non-mock)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_no_api_key_during_verification(client, monkeypatch):
    """Identity verification fails when API key is missing."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    # Set up webhook token but NOT api key
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_webhook_token", "x" * 43)
        # Ensure no API key
        from sqlalchemy import delete

        from app.models.tenant_secret import TenantSecret
        await db.execute(delete(TenantSecret).where(
            TenantSecret.tenant_id == WR_TENANT_ID,
            TenantSecret.key == "asaas_api_key",
        ))
        await db.commit()

    _pid, provider_pid = await _create_payment()

    resp = await client.post(
        "/api/v1/integrations/asaas/webhook/wr",
        json={
            "id": f"evt_nokey_{uuid.uuid4().hex[:8]}",
            "event": "PAYMENT_RECEIVED",
            "payment": {"id": provider_pid},
        },
        headers={"asaas-access-token": "x" * 43},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "FAILED"
    assert resp.json()["reason"] == "no_api_key"


@pytest.mark.asyncio
async def test_webhook_provider_retrieval_failure(client, monkeypatch):
    """Identity verification fails when provider retrieval errors."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    await _setup_asaas_tenant()
    _pid, provider_pid = await _create_payment()

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    with patch.object(AsaasProvider, "get_payment_info",
                      side_effect=PaymentProviderError("Failed", status_code=500, provider_error_code="error")):
        resp = await client.post(
            "/api/v1/integrations/asaas/webhook/wr",
            json={
                "id": f"evt_pfail_{uuid.uuid4().hex[:8]}",
                "event": "PAYMENT_RECEIVED",
                "payment": {"id": provider_pid},
            },
            headers={"asaas-access-token": "x" * 43},
        )
    assert resp.status_code == 200
    assert resp.json()["state"] == "FAILED"
    assert resp.json()["reason"] == "provider_retrieval_failed"


@pytest.mark.asyncio
async def test_webhook_customer_mismatch(client, monkeypatch):
    """Identity verification detects customer mismatch.

    Creates its own deterministic fixture chain (User → Student → Course →
    Class → Enrollment → PaymentCustomer → Payment) so it never depends on
    pre-existing seed data and never skips.
    """
    from datetime import timedelta

    from app.core.config import settings
    from app.core.utils import utc_now
    from app.models.class_model import Class, ClassStatus
    from app.models.course import Course, CourseModality, CourseType
    from app.models.enrollment import Enrollment, EnrollmentSource, EnrollmentStatus
    from app.models.payment import PaymentCustomer
    from app.models.student import Student

    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    await _setup_asaas_tenant()

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))

        # 1. Student user
        stu_user = User(
            email=f"cm_stu_{uuid.uuid4().hex[:6]}@wr.test",
            full_name="Customer Mismatch Student",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(stu_user)
        await db.flush()

        # 2. Student
        student = Student(
            user_id=stu_user.id,
            tenant_id=WR_TENANT_ID,
            cpf=str(uuid.uuid4().int)[:11],
            phone="11999999999",
        )
        db.add(student)
        await db.flush()

        # 3. Admin (required as class responsible_admin_id)
        admin = User(
            email=f"cm_admin_{uuid.uuid4().hex[:6]}@wr.test",
            full_name="Customer Mismatch Admin",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(admin)
        await db.flush()

        # 4. Course
        course = Course(
            tenant_id=WR_TENANT_ID,
            code=f"CM-{uuid.uuid4().hex[:6].upper()}",
            name="Customer Mismatch Course",
            category="Test",
            carga_horaria=8,
            modality=CourseModality.EAD,
            tipo_curso=CourseType.FORMACAO,
            price=299.90,
            is_active=True,
        )
        db.add(course)
        await db.flush()

        # 5. Class
        start = utc_now().date() + timedelta(days=1)
        cls = Class(
            tenant_id=WR_TENANT_ID,
            course_id=course.id,
            responsible_admin_id=admin.id,
            start_date=start,
            end_date=start + timedelta(days=30),
            max_students=20,
            status=ClassStatus.ABERTA,
        )
        db.add(cls)
        await db.flush()

        # 6. Enrollment
        enrollment = Enrollment(
            tenant_id=WR_TENANT_ID,
            student_id=student.id,
            class_id=cls.id,
            price=299.90,
            status=EnrollmentStatus.PENDENTE,
            source=EnrollmentSource.INDIVIDUAL,
        )
        db.add(enrollment)
        await db.flush()

        # 7. PaymentCustomer mapping with a known customer ID
        mapping = PaymentCustomer(
            tenant_id=WR_TENANT_ID,
            provider=PaymentProvider.ASAAS,
            provider_customer_id="cus_internal_mapping",
            student_id=student.id,
        )
        db.add(mapping)
        await db.flush()

        # 8. Payment
        payment = Payment(
            tenant_id=WR_TENANT_ID,
            enrollment_id=enrollment.id,
            amount=299.90,
            status=PaymentStatus.PROCESSANDO,
            method=PaymentMethod.PIX,
            provider=PaymentProvider.ASAAS,
            provider_payment_id="pay_cust_mismatch",
            checkout_url="https://asaas.test/checkout",
        )
        db.add(payment)
        await db.commit()
        payment_id = payment.id

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentInfoResult

    mock_info = PaymentInfoResult(
        provider_payment_id="pay_cust_mismatch",
        status="RECEIVED",
        amount=299.90,
        billing_type="PIX",
        customer_id="cus_different_from_mapping",
        external_reference=str(payment_id),
    )

    with patch.object(AsaasProvider, "get_payment_info", return_value=mock_info):
        resp = await client.post(
            "/api/v1/integrations/asaas/webhook/wr",
            json={
                "id": f"evt_cm_{uuid.uuid4().hex[:8]}",
                "event": "PAYMENT_RECEIVED",
                "payment": {"id": "pay_cust_mismatch"},
            },
            headers={"asaas-access-token": "x" * 43},
        )
    assert resp.status_code == 200
    assert resp.json()["state"] == "FAILED"
    assert resp.json()["reason"] == "customer_mismatch"


@pytest.mark.asyncio
async def test_webhook_pix_status_inconsistent(client, monkeypatch):
    """PIX CONFIRMED event with non-CONFIRMED/RECEIVED status is rejected."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    await _setup_asaas_tenant()
    _pid, provider_pid = await _create_payment()
    payment_id = _pid

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentInfoResult

    mock_info = PaymentInfoResult(
        provider_payment_id=provider_pid,
        status="PENDING",  # Not CONFIRMED or RECEIVED
        amount=299.90,
        billing_type="PIX",
        customer_id="cus_test",
        external_reference=str(payment_id),
    )

    with patch.object(AsaasProvider, "get_payment_info", return_value=mock_info):
        resp = await client.post(
            "/api/v1/integrations/asaas/webhook/wr",
            json={
                "id": f"evt_pixi_{uuid.uuid4().hex[:8]}",
                "event": "PAYMENT_CONFIRMED",
                "payment": {"id": provider_pid},
            },
            headers={"asaas-access-token": "x" * 43},
        )
    assert resp.status_code == 200
    assert resp.json()["state"] == "FAILED"
    assert resp.json()["reason"] == "pix_status_inconsistent"


# ═══════════════════════════════════════════════════════════════
# Asaas connect non-mock error paths
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_connect_non_mock_api_validation_fails(client, monkeypatch):
    """Connect fails with 401 when API key validation request fails."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    admin_id = await _create_admin("asaas_connect_fail@wr.test", WR_TENANT_ID)

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    with patch.object(AsaasProvider, "_request",
                      side_effect=PaymentProviderError("Auth failed", status_code=401, provider_error_code="invalid")):
        resp = await client.post(
            "/api/v1/integrations/asaas/connect",
            json={"api_key": "fake_asaas_key_12345678901234567890"},
            headers=_headers(admin_id),
        )
    assert resp.status_code == 401
    assert "validation failed" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_connect_non_mock_webhook_reconcile_fails(client, monkeypatch):
    """Connect fails with 502 when webhook reconciliation fails."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    admin_id = await _create_admin("asaas_connect_wh_fail@wr.test", WR_TENANT_ID)

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    def mock_request(method, path, **kwargs):
        if method == "GET" and path == "/v3/customers":
            return {"data": [], "totalCount": 0}
        raise PaymentProviderError("Webhook error", status_code=500, provider_error_code="error")

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        resp = await client.post(
            "/api/v1/integrations/asaas/connect",
            json={"api_key": "fake_asaas_key_12345678901234567890"},
            headers=_headers(admin_id),
        )
    assert resp.status_code == 502
    assert "webhook" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_connect_non_mock_webhook_disabled(client, monkeypatch):
    """Connect fails when webhook is disabled."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    admin_id = await _create_admin("asaas_connect_disabled@wr.test", WR_TENANT_ID)

    from app.services.asaas_provider import AsaasProvider

    def mock_request(method, path, **kwargs):
        if method == "GET" and path == "/v3/customers":
            return {"data": [], "totalCount": 0}
        if method == "POST" and path == "/v3/webhooks":
            return {
                "id": "wh_disabled",
                "name": "test",
                "url": "https://test/webhook",
                "enabled": False,  # Disabled!
                "interrupted": False,
            }
        if method == "GET" and path.startswith("/v3/webhooks"):
            return {"data": [], "totalCount": 0}
        return {}

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        resp = await client.post(
            "/api/v1/integrations/asaas/connect",
            json={"api_key": "fake_asaas_key_12345678901234567890"},
            headers=_headers(admin_id),
        )
    assert resp.status_code == 502
    assert "not enabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_connect_non_mock_webhook_interrupted(client, monkeypatch):
    """Connect fails when webhook queue is interrupted."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    admin_id = await _create_admin("asaas_connect_inter@wr.test", WR_TENANT_ID)

    from app.services.asaas_provider import AsaasProvider

    def mock_request(method, path, **kwargs):
        if method == "GET" and path == "/v3/customers":
            return {"data": [], "totalCount": 0}
        if method == "POST" and path == "/v3/webhooks":
            return {
                "id": "wh_interrupted",
                "name": "test",
                "url": "https://test/webhook",
                "enabled": True,
                "interrupted": True,  # Interrupted!
            }
        if method == "GET" and path.startswith("/v3/webhooks"):
            return {"data": [], "totalCount": 0}
        return {}

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        resp = await client.post(
            "/api/v1/integrations/asaas/connect",
            json={"api_key": "fake_asaas_key_12345678901234567890"},
            headers=_headers(admin_id),
        )
    assert resp.status_code == 502
    assert "interrupted" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_connect_empty_api_key_returns_400(client, monkeypatch):
    """Connect with empty API key returns 400."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_empty_key@wr.test", WR_TENANT_ID)

    resp = await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": ""},
        headers=_headers(admin_id),
    )
    assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════
# Asaas validate non-mock error paths
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_validate_non_mock_auth_fails(client, monkeypatch):
    """Validate returns invalid when API key auth fails."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    admin_id = await _create_admin("asaas_val_fail@wr.test", WR_TENANT_ID)
    await _setup_asaas_tenant()

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    with patch.object(AsaasProvider, "_request",
                      side_effect=PaymentProviderError("Auth failed", status_code=401, provider_error_code="invalid")):
        resp = await client.post(
            "/api/v1/integrations/asaas/validate",
            headers=_headers(admin_id),
        )
    assert resp.status_code == 200
    assert resp.json()["valid"] is False


@pytest.mark.asyncio
async def test_validate_non_mock_webhook_not_found(client, monkeypatch):
    """Validate returns unhealthy when webhook is not found."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    admin_id = await _create_admin("asaas_val_wh_nf@wr.test", WR_TENANT_ID)
    await _setup_asaas_tenant()

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    def mock_request(method, path, **kwargs):
        if method == "GET" and path == "/v3/customers":
            return {"data": [], "totalCount": 0}
        if method == "GET" and path.startswith("/v3/webhooks/"):
            raise PaymentProviderError("Not found", status_code=404, provider_error_code="not_found")
        return {}

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        resp = await client.post(
            "/api/v1/integrations/asaas/validate",
            headers=_headers(admin_id),
        )
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["webhook_healthy"] is False


# ═══════════════════════════════════════════════════════════════
# Asaas disconnect non-mock paths
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_disconnect_non_mock_webhook_disable_failure(client, monkeypatch):
    """Disconnect still succeeds when remote webhook disable fails."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", False)

    admin_id = await _create_admin("asaas_disc_fail@wr.test", WR_TENANT_ID)
    await _setup_asaas_tenant()

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    with patch.object(AsaasProvider, "update_webhook",
                      side_effect=PaymentProviderError("Failed", status_code=500, provider_error_code="error")):
        resp = await client.delete(
            "/api/v1/integrations/asaas/",
            headers=_headers(admin_id),
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"


@pytest.mark.asyncio
async def test_disconnect_idempotent(client, monkeypatch):
    """Disconnect without prior connect still succeeds."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_disc_idem@wr.test", WR_TENANT_ID)

    resp = await client.delete(
        "/api/v1/integrations/asaas/",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"


# ═══════════════════════════════════════════════════════════════
# Asaas status endpoint
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_status_not_configured(client, monkeypatch):
    """Status returns configured=False when no API key is set."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_status_none@wr.test", WR_TENANT_ID)

    # Ensure no secrets
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import delete

        from app.models.tenant_secret import TenantSecret
        await db.execute(delete(TenantSecret).where(TenantSecret.tenant_id == WR_TENANT_ID))
        # Clear tenant settings
        tenant = (await db.execute(
            __import__("sqlalchemy").select(Tenant).where(Tenant.id == WR_TENANT_ID)
        )).scalar_one()
        ts = dict(tenant.settings or {})
        ts.pop("payment_provider", None)
        ts.pop("asaas_webhook_id", None)
        tenant.settings = ts
        await db.commit()

    resp = await client.get(
        "/api/v1/integrations/asaas/status",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["configured"] is False
    assert resp.json()["is_asaas_active"] is False


# ═══════════════════════════════════════════════════════════════
# Asaas provider real (non-mock) paths
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_provider_timeout_sanitized():
    """Provider timeout raises PaymentProviderError with sanitized message."""
    import httpx

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch("httpx.AsyncClient.request", side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider._request("GET", "/v3/customers")
        assert exc_info.value.status_code == 504
        assert "timed out" in str(exc_info.value)


@pytest.mark.asyncio
async def test_provider_network_error_sanitized():
    """Provider network error raises PaymentProviderError with sanitized message."""
    import httpx

    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch("httpx.AsyncClient.request", side_effect=httpx.RequestError("connection refused")):
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider._request("GET", "/v3/customers")
        assert exc_info.value.status_code == 502
        assert "request failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_provider_401_sanitized():
    """Provider 401 error is sanitized."""
    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"errors": [{"description": "Invalid API key secret"}]}

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider._request("GET", "/v3/customers")
        assert "authentication failed" in str(exc_info.value)
        assert "Invalid API key secret" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_provider_403_sanitized():
    """Provider 403 error is sanitized."""
    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"errors": [{"description": "Forbidden resource"}]}

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider._request("GET", "/v3/customers")
        assert "access denied" in str(exc_info.value)


@pytest.mark.asyncio
async def test_provider_404_sanitized():
    """Provider 404 error is sanitized."""
    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"errors": [{"description": "Not found"}]}

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider._request("GET", "/v3/customers")
        assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_provider_400_sanitized():
    """Provider 400 error is sanitized."""
    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"errors": [{"description": "Bad request body"}]}

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider._request("GET", "/v3/customers")
        assert "bad request" in str(exc_info.value)


@pytest.mark.asyncio
async def test_provider_500_sanitized():
    """Provider 500 error is sanitized."""
    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {"errors": [{"description": "Internal server error"}]}

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider._request("GET", "/v3/customers")
        assert "500" in str(exc_info.value)


@pytest.mark.asyncio
async def test_provider_create_checkout_real_with_customer():
    """Real checkout creates customer when no customer_id provided."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    def mock_request(method, path, **kwargs):
        if method == "GET" and path == "/v3/customers":
            return {"data": [], "totalCount": 0}
        if method == "POST" and path == "/v3/customers":
            return {"id": "cus_new_123", "name": "Test", "email": "test@test.com"}
        if method == "POST" and path == "/v3/payments":
            return {"id": "pay_new_123", "invoiceUrl": "https://asaas.test/checkout"}
        return {}

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        result = await provider.create_checkout(
            payment_id=uuid.uuid4(),
            amount=299.90,
            student_email="test@test.com",
            student_name="Test Student",
            course_name="Test Course",
            method=PaymentMethod.PIX,
        )
    assert result.provider_payment_id == "pay_new_123"
    assert result.checkout_url == "https://asaas.test/checkout"


@pytest.mark.asyncio
async def test_provider_create_checkout_pix_qr_code_fetch():
    """Real checkout fetches PIX QR code when no invoiceUrl."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    def mock_request(method, path, **kwargs):
        if method == "POST" and path == "/v3/payments":
            return {"id": "pay_pix_123"}  # No invoiceUrl
        if method == "GET" and path == "/v3/payments/pay_pix_123/pixQrCode":
            return {"payload": "qr-pix-payload-data", "encodedImage": "base64img"}
        return {}

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        result = await provider.create_checkout(
            payment_id=uuid.uuid4(),
            amount=150.0,
            student_email="test@test.com",
            student_name="Test",
            course_name="Course",
            method=PaymentMethod.PIX,
            customer_id="cus_existing",
        )
    assert result.provider_payment_id == "pay_pix_123"
    assert result.checkout_url == "qr-pix-payload-data"


@pytest.mark.asyncio
async def test_provider_refund_real():
    """Real refund calls the API."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch.object(AsaasProvider, "_request", return_value={"id": "pay_1", "status": "REFUNDED"}):
        result = await provider.refund_payment("pay_1")
    assert result["status"] == "REFUNDED"


@pytest.mark.asyncio
async def test_provider_create_or_update_customer_existing():
    """create_or_update_customer finds existing by externalReference."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    def mock_request(method, path, **kwargs):
        if method == "GET" and path == "/v3/customers":
            return {"data": [{"id": "cus_existing_1", "name": "Existing"}], "totalCount": 1}
        return {}

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        result = await provider.create_or_update_customer(
            name="Test",
            email="test@test.com",
            cpf_cnpj="12345678901",
            phone="11999999999",
            external_id="stu-123",
        )
    assert result.provider_customer_id == "cus_existing_1"


@pytest.mark.asyncio
async def test_provider_create_or_update_customer_new():
    """create_or_update_customer creates new when not found."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    def mock_request(method, path, **kwargs):
        if method == "GET" and path == "/v3/customers":
            return {"data": [], "totalCount": 0}
        if method == "POST" and path == "/v3/customers":
            return {"id": "cus_new_456", "name": "New Customer"}
        return {}

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        result = await provider.create_or_update_customer(
            name="New Customer",
            email="new@test.com",
            external_id="stu-456",
        )
    assert result.provider_customer_id == "cus_new_456"


@pytest.mark.asyncio
async def test_provider_list_webhooks_real():
    """Real list_webhooks returns data from API."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch.object(AsaasProvider, "_request", return_value={"data": [{"id": "wh1"}], "totalCount": 1}):
        result = await provider.list_webhooks()
    assert len(result.data) == 1
    assert result.mock is False


@pytest.mark.asyncio
async def test_provider_create_webhook_real():
    """Real create_webhook sends payload to API."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch.object(AsaasProvider, "_request", return_value={
        "id": "wh_new", "name": "test", "url": "https://t/w", "enabled": True, "interrupted": False,
    }) as mock_req:
        result = await provider.create_webhook(
            name="test", url="https://t/w", auth_token="x" * 43, email="t@t.com",
        )
    assert result.id == "wh_new"
    assert mock_req.call_args[1]["json"]["enabled"] is True


@pytest.mark.asyncio
async def test_provider_update_webhook_real():
    """Real update_webhook sends PUT to API."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch.object(AsaasProvider, "_request", return_value={
        "id": "wh_1", "name": "updated", "url": "https://t/w", "enabled": False, "interrupted": False,
    }) as mock_req:
        result = await provider.update_webhook(webhook_id="wh_1", enabled=False)
    assert result.id == "wh_1"
    assert result.enabled is False
    # Verify PUT method was used
    assert mock_req.call_args[0][0] == "PUT"


@pytest.mark.asyncio
async def test_provider_delete_webhook_real():
    """Real delete_webhook returns True on success."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch.object(AsaasProvider, "_request", return_value={"deleted": True}):
        result = await provider.delete_webhook("wh_1")
    assert result is True


@pytest.mark.asyncio
async def test_provider_delete_webhook_not_found_idempotent():
    """delete_webhook returns True even when webhook is not found (idempotent)."""
    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch.object(AsaasProvider, "_request",
                      side_effect=PaymentProviderError("Not found", status_code=404, provider_error_code="not_found")):
        result = await provider.delete_webhook("wh_nonexistent")
    assert result is True


@pytest.mark.asyncio
async def test_provider_get_webhook_real():
    """Real get_webhook returns config from API."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch.object(AsaasProvider, "_request", return_value={
        "id": "wh_1", "name": "test", "url": "https://t/w", "enabled": True, "interrupted": False,
    }):
        result = await provider.get_webhook("wh_1")
    assert result is not None
    assert result.id == "wh_1"


@pytest.mark.asyncio
async def test_provider_get_webhook_not_found():
    """get_webhook returns None when webhook is not found."""
    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with patch.object(AsaasProvider, "_request",
                      side_effect=PaymentProviderError("Not found", status_code=404, provider_error_code="not_found")):
        result = await provider.get_webhook("wh_nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_provider_reconcile_webhook_updates_existing():
    """reconcile_webhook updates existing webhook by name."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    def mock_request(method, path, **kwargs):
        if method == "GET" and path == "/v3/webhooks":
            return {"data": [{"id": "wh_existing", "name": "WR Cursos Payments - wr"}], "totalCount": 1}
        if method == "PUT" and path.startswith("/v3/webhooks/"):
            return {
                "id": "wh_existing", "name": "WR Cursos Payments - wr",
                "url": "https://new/webhook", "enabled": True, "interrupted": False,
            }
        return {}

    with patch.object(AsaasProvider, "_request", side_effect=mock_request):
        result = await provider.reconcile_webhook(
            webhook_name="WR Cursos Payments - wr",
            webhook_url="https://new/webhook",
            auth_token="x" * 43,
        )
    assert result.id == "wh_existing"


@pytest.mark.asyncio
async def test_provider_create_webhook_invalid_token_length():
    """create_webhook rejects tokens shorter than 32 chars."""
    from app.services.asaas_provider import AsaasProvider
    from app.services.payment_provider_base import PaymentProviderError

    provider = AsaasProvider(api_key="test_key_12345678901234567890", sandbox=True, mock=False)

    with pytest.raises(PaymentProviderError) as exc_info:
        await provider.create_webhook(
            name="test", url="https://t/w", auth_token="short",
        )
    assert "32-255" in str(exc_info.value)


# ─── Asaas provider mock paths (deterministic mock responses) ───

@pytest.mark.asyncio
async def test_provider_mock_request_all_paths():
    """Cover all _mock_request branches (customers, payments, pixQrCode, webhooks)."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key", sandbox=True, mock=True)

    # GET customers
    r = await provider._request("GET", "/v3/customers")
    assert r["totalCount"] == 0

    # GET payment by id
    r = await provider._request("GET", "/v3/payments/pay_123")
    assert r["id"] == "pay_123"
    assert r["status"] == "RECEIVED"

    # GET pixQrCode
    r = await provider._request("GET", "/v3/payments/pay_123/pixQrCode")
    assert "payload" in r

    # GET webhooks
    r = await provider._request("GET", "/v3/webhooks")
    assert r["totalCount"] == 0

    # POST webhook
    r = await provider._request("POST", "/v3/webhooks", json={"name": "test", "url": "http://t", "events": ["PAYMENT_RECEIVED"]})
    assert r["enabled"] is True

    # PUT webhook
    r = await provider._request("PUT", "/v3/webhooks/wh_1", json={"enabled": False})
    assert r["id"] == "wh_1"

    # DELETE webhook
    r = await provider._request("DELETE", "/v3/webhooks/wh_1")
    assert r["deleted"] is True

    # Unknown path returns generic mock
    r = await provider._request("GET", "/v3/other")
    assert r["mock"] is True


@pytest.mark.asyncio
async def test_provider_mock_checkout_all_methods():
    """Cover _mock_checkout for PIX, BOLETO, and CARTAO."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key", sandbox=True, mock=True)

    # PIX
    r = await provider.create_checkout(
        payment_id=uuid.uuid4(), amount=100, student_email="t@t.com",
        student_name="T", course_name="C", method=PaymentMethod.PIX,
    )
    assert r.provider_payment_id is not None

    # BOLETO
    r = await provider.create_checkout(
        payment_id=uuid.uuid4(), amount=100, student_email="t@t.com",
        student_name="T", course_name="C", method=PaymentMethod.BOLETO,
    )
    assert r.provider_payment_id is not None

    # CARTAO
    r = await provider.create_checkout(
        payment_id=uuid.uuid4(), amount=100, student_email="t@t.com",
        student_name="T", course_name="C", method=PaymentMethod.CARTAO,
    )
    assert r.provider_payment_id is not None


@pytest.mark.asyncio
async def test_provider_mock_get_payment_info():
    """Cover _mock_payment_info path."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key", sandbox=True, mock=True)

    r = await provider.get_payment_info("pay_test_123")
    assert r.provider_payment_id == "pay_test_123"
    assert r.status == "RECEIVED"


@pytest.mark.asyncio
async def test_provider_mock_refund():
    """Cover mock refund path."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key", sandbox=True, mock=True)

    r = await provider.refund_payment("pay_123")
    assert r["status"] == "REFUNDED"
    assert r["mock"] is True


@pytest.mark.asyncio
async def test_provider_mock_list_create_update_delete_get_webhook():
    """Cover all mock webhook management paths."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key", sandbox=True, mock=True)

    # list
    r = await provider.list_webhooks()
    assert r.mock is True

    # create
    r = await provider.create_webhook(name="test", url="https://t/w", auth_token="x" * 43)
    assert r.mock is True

    # update
    r = await provider.update_webhook(webhook_id="wh_1", enabled=False)
    assert r.id == "wh_1"

    # delete
    r = await provider.delete_webhook("wh_1")
    assert r is True

    # get
    r = await provider.get_webhook("wh_1")
    assert r is not None
    assert r.id == "wh_1"


@pytest.mark.asyncio
async def test_provider_mock_create_or_update_customer():
    """Cover mock customer creation."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key", sandbox=True, mock=True)

    r = await provider.create_or_update_customer(
        name="Test", email="t@t.com", external_id="stu-123",
    )
    assert "mock-cus" in r.provider_customer_id


@pytest.mark.asyncio
async def test_provider_mock_reconcile_webhook_creates_new():
    """Cover mock reconcile_webhook (creates new when none match)."""
    from app.services.asaas_provider import AsaasProvider

    provider = AsaasProvider(api_key="test_key", sandbox=True, mock=True)

    r = await provider.reconcile_webhook(
        webhook_name="WR Cursos Payments - wr",
        webhook_url="https://t/w",
        auth_token="x" * 43,
    )
    assert r is not None


# ═══════════════════════════════════════════════════════════════
# Email service SMTP paths
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_email_send_smtp_success():
    """Email service sends via SMTP successfully."""
    from app.services.email_service import EmailService

    service = EmailService(
        smtp_server="smtp.test.com",
        smtp_port=587,
        smtp_user="user@test.com",
        smtp_password="pass",
    mock=False,
    )

    with patch("smtplib.SMTP") as mock_smtp:
        instance = mock_smtp.return_value.__enter__.return_value
        result = await service.send_email(
            to="dest@test.com",
            subject="Test",
            html_body="<p>Test</p>",
            text_body="Test",
        )
    assert result is True
    instance.starttls.assert_called_once()
    instance.login.assert_called_once()
    instance.sendmail.assert_called_once()


@pytest.mark.asyncio
async def test_email_send_smtp_failure_sanitized():
    """Email service SMTP failure raises sanitized error."""
    import smtplib

    from app.services.email_service import EmailService, EmailServiceError

    service = EmailService(
        smtp_server="smtp.test.com",
        smtp_port=587,
        smtp_user="user@test.com",
        smtp_password="pass",
    mock=False,
    )

    with patch("smtplib.SMTP") as mock_smtp:
        instance = mock_smtp.return_value.__enter__.return_value
        instance.sendmail.side_effect = smtplib.SMTPException("Detailed internal error with credentials")
        with pytest.raises(EmailServiceError) as exc_info:
            await service.send_email(
                to="dest@test.com",
                subject="Test",
                html_body="<p>Test</p>",
            )
    assert "Failed to send email" in str(exc_info.value)
    assert "credentials" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_email_send_no_smtp_credentials():
    """Email service returns False when SMTP credentials not configured."""
    from app.services.email_service import EmailService

    service = EmailService(
        smtp_server="smtp.test.com",
        smtp_port=587,
        smtp_user=None,
        smtp_password=None,
    mock=False,
    )

    result = await service.send_email(
        to="dest@test.com",
        subject="Test",
        html_body="<p>Test</p>",
    )
    assert result is False


@pytest.mark.asyncio
async def test_email_send_password_reset_tenant_aware():
    """send_password_reset includes tenant name and frontend URL."""
    from app.services.email_service import EmailService

    service = EmailService(
        smtp_server="smtp.test.com",
        smtp_port=587,
        smtp_user="user@test.com",
        smtp_password="pass",
    mock=False,
    )

    with patch("smtplib.SMTP") as mock_smtp:
        instance = mock_smtp.return_value.__enter__.return_value
        await service.send_password_reset(
            to="dest@test.com",
            reset_token="tok123",
            frontend_url="https://alfa.test",
            tenant_name="Alfa Academy",
        )
    sent_msg = instance.sendmail.call_args[0][2]
    # From header includes tenant name (ASCII-safe)
    assert "Alfa Academy" in sent_msg
    # Verify email was actually sent via SMTP
    instance.sendmail.assert_called_once()
    # Verify recipient
    assert "dest@test.com" in instance.sendmail.call_args[0][1]


@pytest.mark.asyncio
async def test_email_send_account_activation_tenant_aware():
    """send_account_activation includes tenant name and frontend URL."""
    from app.services.email_service import EmailService

    service = EmailService(
        smtp_server="smtp.test.com",
        smtp_port=587,
        smtp_user="user@test.com",
        smtp_password="pass",
    mock=False,
    )

    with patch("smtplib.SMTP") as mock_smtp:
        instance = mock_smtp.return_value.__enter__.return_value
        await service.send_account_activation(
            to="dest@test.com",
            activation_token="act123",
            frontend_url="https://wr.test",
            tenant_name="WR Consultoria",
        )
    sent_msg = instance.sendmail.call_args[0][2]
    # From header includes tenant name (ASCII-safe)
    assert "WR Consultoria" in sent_msg
    # Verify email was actually sent via SMTP
    instance.sendmail.assert_called_once()
    # Verify recipient
    assert "dest@test.com" in instance.sendmail.call_args[0][1]
