"""Tests for financial secrets write-only enforcement.

Protected keys (asaas_api_key, mercado_pago_access_token, smtp_password,
storage_secret_key, asaas_webhook_token) can be configured, replaced,
deleted, and validated — but NEVER revealed in plaintext via the API.
"""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.tenant_secret import TenantSecret
from app.models.user import User, UserRole
from app.services.secret_crypto import encrypt


async def _create_super_admin(email, tenant_id):
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        user = User(
            email=email,
            full_name=f"Super {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


def _super_headers(user_id, tenant_id=WR_TENANT_ID):
    token = create_access_token(
        {"sub": str(user_id), "role": "super_admin", "tenant_id": str(tenant_id)}
    )
    return {"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"}


async def _store_secret(tenant_id, key, value):
    async with AsyncSessionLocal() as db:
        await db.execute(text("SET LOCAL app.bypass_rls = '1'"))
        secret = TenantSecret(
            tenant_id=tenant_id,
            key=key,
            encrypted_value=encrypt(value),
            description=f"Test {key}",
        )
        db.add(secret)
        await db.commit()
        await db.refresh(secret)
        return secret.id


@pytest.mark.asyncio
async def test_asaas_api_key_not_revealable(client):
    """asaas_api_key is write-only — reveal returns 403."""
    sa_id = await _create_super_admin("sa_reveal_asaas@wr.test", WR_TENANT_ID)
    secret_id = await _store_secret(WR_TENANT_ID, "asaas_api_key", "secret_asaas_key_123")

    resp = await client.get(
        f"/api/v1/super-admin/tenants/{WR_TENANT_ID}/secrets/{secret_id}/reveal",
        headers=_super_headers(sa_id),
    )
    assert resp.status_code == 403
    assert "write-only" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mercado_pago_token_not_revealable(client):
    """mercado_pago_access_token is write-only — reveal returns 403."""
    sa_id = await _create_super_admin("sa_reveal_mp@wr.test", WR_TENANT_ID)
    secret_id = await _store_secret(WR_TENANT_ID, "mercado_pago_access_token", "MP_TOKEN_123")

    resp = await client.get(
        f"/api/v1/super-admin/tenants/{WR_TENANT_ID}/secrets/{secret_id}/reveal",
        headers=_super_headers(sa_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_smtp_password_not_revealable(client):
    """smtp_password is write-only — reveal returns 403."""
    sa_id = await _create_super_admin("sa_reveal_smtp@wr.test", WR_TENANT_ID)
    secret_id = await _store_secret(WR_TENANT_ID, "smtp_password", "smtp_pass_123")

    resp = await client.get(
        f"/api/v1/super-admin/tenants/{WR_TENANT_ID}/secrets/{secret_id}/reveal",
        headers=_super_headers(sa_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_storage_secret_key_not_revealable(client):
    """storage_secret_key is write-only — reveal returns 403."""
    sa_id = await _create_super_admin("sa_reveal_storage@wr.test", WR_TENANT_ID)
    secret_id = await _store_secret(WR_TENANT_ID, "storage_secret_key", "storage_key_123")

    resp = await client.get(
        f"/api/v1/super-admin/tenants/{WR_TENANT_ID}/secrets/{secret_id}/reveal",
        headers=_super_headers(sa_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_asaas_webhook_token_not_revealable(client):
    """asaas_webhook_token is write-only — reveal returns 403."""
    sa_id = await _create_super_admin("sa_reveal_wh@wr.test", WR_TENANT_ID)
    secret_id = await _store_secret(WR_TENANT_ID, "asaas_webhook_token", "wh_token_123")

    resp = await client.get(
        f"/api/v1/super-admin/tenants/{WR_TENANT_ID}/secrets/{secret_id}/reveal",
        headers=_super_headers(sa_id),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_protected_secret_still_revealable(client):
    """Non-protected secrets can still be revealed by SUPER_ADMIN."""
    sa_id = await _create_super_admin("sa_reveal_ok@wr.test", WR_TENANT_ID)
    secret_id = await _store_secret(WR_TENANT_ID, "custom_api_key", "custom_value_123")

    resp = await client.get(
        f"/api/v1/super-admin/tenants/{WR_TENANT_ID}/secrets/{secret_id}/reveal",
        headers=_super_headers(sa_id),
    )
    assert resp.status_code == 200
    assert resp.json()["value"] == "custom_value_123"
