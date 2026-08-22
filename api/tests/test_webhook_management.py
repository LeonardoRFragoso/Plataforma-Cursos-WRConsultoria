"""Tests for webhook management via connect/validate/reconcile flows."""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole
from app.services.tenant_secret_service import set_tenant_secret


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


async def _setup_configured_tenant():
    """Set up tenant with API key and webhook token."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_api_key", "fake_key_12345678901234567890")
        await set_tenant_secret(db, WR_TENANT_ID, "asaas_webhook_token", "x" * 43)
        await db.commit()


@pytest.mark.asyncio
async def test_connect_creates_webhook_in_mock(client, monkeypatch):
    """Connect in mock mode creates a webhook and stores its ID."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_connect_wh@wr.test", WR_TENANT_ID)

    resp = await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_asaas_key_12345678901234567890"},
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "connected"
    assert data["webhook_configured"] is True
    assert data["webhook_id"] is not None
    assert data["webhook_id"].startswith("mock-wh-")


@pytest.mark.asyncio
async def test_validate_checks_webhook_health(client, monkeypatch):
    """Validate checks webhook health and updates last_validation_at."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_val_health@wr.test", WR_TENANT_ID)
    await _setup_configured_tenant()

    # Connect first to create webhook metadata
    await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_key_12345678901234567890"},
        headers=_headers(admin_id),
    )

    # Validate
    resp = await client.post(
        "/api/v1/integrations/asaas/validate",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["webhook_healthy"] is True


@pytest.mark.asyncio
async def test_disconnect_disables_webhook(client, monkeypatch):
    """Disconnect disables the remote webhook and clears metadata."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_disc_wh@wr.test", WR_TENANT_ID)

    # Connect first
    await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_key_12345678901234567890"},
        headers=_headers(admin_id),
    )

    # Disconnect
    resp = await client.delete(
        "/api/v1/integrations/asaas/",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"


@pytest.mark.asyncio
async def test_status_shows_webhook_details(client, monkeypatch):
    """Status endpoint shows webhook details after connect."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_status_det@wr.test", WR_TENANT_ID)

    # Connect first
    await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_key_12345678901234567890"},
        headers=_headers(admin_id),
    )

    resp = await client.get(
        "/api/v1/integrations/asaas/status",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["webhook_configured"] is True
    assert data["webhook_enabled"] is True
    assert data["webhook_interrupted"] is False
    assert data["webhook_id"] is not None
    assert data["last_validation_at"] is not None


@pytest.mark.asyncio
async def test_webhook_endpoints_require_admin(client, monkeypatch):
    """Asaas integration endpoints require admin role."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        student = User(
            email="student_wh2@wr.test",
            full_name="Student",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(student)
        await db.commit()
        await db.refresh(student)
        student_id = student.id

    # Status should be forbidden for students
    resp = await client.get(
        "/api/v1/integrations/asaas/status",
        headers=_headers(student_id, "student"),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_validate_without_api_key_returns_400(client, monkeypatch):
    """Validate without API key returns 400."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_val_nokey@wr.test", WR_TENANT_ID)
    # No API key set up

    resp = await client.post(
        "/api/v1/integrations/asaas/validate",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"].lower()
