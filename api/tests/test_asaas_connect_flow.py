"""Tests for Asaas connect/disconnect/validate flows and webhook management."""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.tenant import Tenant
from app.models.user import User, UserRole


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


@pytest.mark.asyncio
async def test_connect_mock_mode_stores_webhook_metadata(client, monkeypatch):
    """Connect in mock mode stores webhook_id and metadata in tenant settings."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_connect_meta@wr.test", WR_TENANT_ID)

    resp = await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_asaas_key_12345678901234567890"},
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"
    assert resp.json()["webhook_configured"] is True
    assert resp.json()["webhook_id"] is not None

    # Verify tenant settings were updated
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        tenant = (await db.execute(select(Tenant).where(Tenant.id == WR_TENANT_ID))).scalar_one()
        ts = tenant.settings or {}
        assert ts.get("payment_provider") == "ASAAS"
        assert ts.get("asaas_webhook_id") is not None
        assert ts.get("asaas_webhook_enabled") is True
        assert ts.get("asaas_webhook_interrupted") is False
        assert ts.get("asaas_last_validation_at") is not None


@pytest.mark.asyncio
async def test_disconnect_clears_webhook_metadata(client, monkeypatch):
    """Disconnect clears webhook metadata from tenant settings."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_disc_meta@wr.test", WR_TENANT_ID)

    # Connect first
    await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_asaas_key_12345678901234567890"},
        headers=_headers(admin_id),
    )

    # Disconnect
    resp = await client.delete(
        "/api/v1/integrations/asaas/",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"

    # Verify tenant settings were cleared
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        from sqlalchemy import select
        tenant = (await db.execute(select(Tenant).where(Tenant.id == WR_TENANT_ID))).scalar_one()
        ts = tenant.settings or {}
        assert "payment_provider" not in ts
        assert "asaas_webhook_id" not in ts
        assert "asaas_webhook_enabled" not in ts
        assert "asaas_last_validation_at" not in ts


@pytest.mark.asyncio
async def test_validate_mock_mode_returns_valid(client, monkeypatch):
    """Validate in mock mode returns valid."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_val@wr.test", WR_TENANT_ID)

    # Connect first
    await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_asaas_key_12345678901234567890"},
        headers=_headers(admin_id),
    )

    # Validate
    resp = await client.post(
        "/api/v1/integrations/asaas/validate",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["webhook_healthy"] is True


@pytest.mark.asyncio
async def test_validate_not_configured_returns_400(client, monkeypatch):
    """Validate without API key returns 400."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_val_none@wr.test", WR_TENANT_ID)

    resp = await client.post(
        "/api/v1/integrations/asaas/validate",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_status_returns_all_fields(client, monkeypatch):
    """Status endpoint returns all required fields."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_status_full@wr.test", WR_TENANT_ID)

    # Connect first
    await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "fake_asaas_key_12345678901234567890"},
        headers=_headers(admin_id),
    )

    resp = await client.get(
        "/api/v1/integrations/asaas/status",
        headers=_headers(admin_id),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "configured" in data
    assert "connection_valid" in data
    assert "webhook_configured" in data
    assert "webhook_enabled" in data
    assert "webhook_interrupted" in data
    assert "webhook_id" in data
    assert "active_provider" in data
    assert "is_asaas_active" in data
    assert "last_validation_at" in data
    assert "last_webhook_at" in data
    assert data["configured"] is True
    assert data["connection_valid"] is True
    assert data["webhook_configured"] is True
    assert data["webhook_enabled"] is True
    assert data["webhook_interrupted"] is False
    assert data["active_provider"] == "ASAAS"
    assert data["is_asaas_active"] is True


@pytest.mark.asyncio
async def test_connect_short_key_rejected(client, monkeypatch):
    """Connect rejects keys that are too short."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ASAAS_MOCK_MODE", True)

    admin_id = await _create_admin("asaas_short_key@wr.test", WR_TENANT_ID)

    resp = await client.post(
        "/api/v1/integrations/asaas/connect",
        json={"api_key": "short"},
        headers=_headers(admin_id),
    )
    assert resp.status_code == 400
