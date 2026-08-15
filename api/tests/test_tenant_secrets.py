import uuid
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.api.routes.super_admin import super_reveal_tenant_secret
from app.api.routes.tenant_secrets import (
    create_secret,
    delete_secret,
    list_secrets,
    update_secret,
)
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant, TenantStatus
from app.models.tenant_secret import TenantSecret
from app.schemas.tenant_secret import TenantSecretCreate, TenantSecretUpdate
from app.services.secret_crypto import decrypt, encrypt


@asynccontextmanager
async def tenant_context():
    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        yield
    finally:
        current_tenant_id.reset(token)


def test_encrypt_decrypt_roundtrip():
    plaintext = "sk-test-1234567890"
    token = encrypt(plaintext)
    assert token != plaintext
    assert decrypt(token) == plaintext


def test_decrypt_invalid_token_raises():
    with pytest.raises(ValueError):
        decrypt("not-a-valid-fernet-token")


def test_encrypt_none_returns_none():
    assert encrypt(None) is None
    assert decrypt(None) is None


@pytest.mark.asyncio
async def test_create_and_list_secret():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = TenantSecretCreate(
            key="MERCADO_PAGO_ACCESS_TOKEN",
            value="APP_USR-1234567890-abc",
            description="MP access token",
        )
        result = await create_secret(
            data, db, {"user_id": str(uuid.uuid4()), "role": "admin"}
        )
        assert result.key == "MERCADO_PAGO_ACCESS_TOKEN"
        # Resposta nunca expõe o valor plano
        assert not hasattr(result, "value") or getattr(result, "value", None) is None

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        secrets = await list_secrets(
            db, {"user_id": str(uuid.uuid4()), "role": "admin"}
        )
        assert any(s.key == "MERCADO_PAGO_ACCESS_TOKEN" for s in secrets)


@pytest.mark.asyncio
async def test_create_secret_duplicate_key_conflict():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = TenantSecretCreate(key="DUP_KEY", value="v1")
        await create_secret(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})

        with pytest.raises(HTTPException) as exc:
            await create_secret(
                TenantSecretCreate(key="DUP_KEY", value="v2"),
                db,
                {"user_id": str(uuid.uuid4()), "role": "admin"},
            )
        assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_update_secret():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        created = await create_secret(
            TenantSecretCreate(key="UPD_KEY", value="v1"),
            db,
            {"user_id": str(uuid.uuid4()), "role": "admin"},
        )
        secret_id = created.id

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        updated = await update_secret(
            secret_id,
            TenantSecretUpdate(value="v2", description="updated"),
            db,
            {"user_id": str(uuid.uuid4()), "role": "admin"},
        )
        assert updated.description == "updated"

        # Verifica que o valor foi re-cifrado
        secret = await db.get(TenantSecret, secret_id)
        assert decrypt(secret.encrypted_value) == "v2"


@pytest.mark.asyncio
async def test_delete_secret():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        created = await create_secret(
            TenantSecretCreate(key="DEL_KEY", value="v1"),
            db,
            {"user_id": str(uuid.uuid4()), "role": "admin"},
        )
        secret_id = created.id

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        await delete_secret(
            secret_id, db, {"user_id": str(uuid.uuid4()), "role": "admin"}
        )
        secret = await db.get(TenantSecret, secret_id)
        assert secret is None


@pytest.mark.asyncio
async def test_tenant_a_cannot_access_tenant_b_secret():
    """Tenant A não acessa secret de Tenant B (escopo tenant)."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant_b = Tenant(
            name="B",
            slug="tenant-b",
            status=TenantStatus.ACTIVE,
            contact_name="B",
            contact_email="b@test.com",
        )
        db.add(tenant_b)
        await db.commit()
        await db.refresh(tenant_b)
        secret_b = TenantSecret(
            tenant_id=tenant_b.id,
            key="SECRET_B",
            encrypted_value=encrypt("v-b"),
        )
        db.add(secret_b)
        await db.commit()
        await db.refresh(secret_b)
        secret_b_id = secret_b.id
        tenant_b_id = tenant_b.id

    # Tenant A (WR) tenta acessar secret do Tenant B -> 404
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        with pytest.raises(HTTPException) as exc:
            await update_secret(
                secret_b_id,
                TenantSecretUpdate(value="hack"),
                db,
                {"user_id": str(uuid.uuid4()), "role": "admin"},
            )
        assert exc.value.status_code == 404
        _ = tenant_b_id  # mantém referência


@pytest.mark.asyncio
async def test_super_admin_reveal_secret_plaintext():
    """SUPER_ADMIN revela o valor plano de um secret."""
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        created = await create_secret(
            TenantSecretCreate(key="REVEAL_KEY", value="plaintext-value-123"),
            db,
            {"user_id": str(uuid.uuid4()), "role": "admin"},
        )
        secret_id = created.id

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        revealed = await super_reveal_tenant_secret(
            WR_TENANT_ID,
            secret_id,
            db,
            {"user_id": str(uuid.uuid4()), "role": "super_admin"},
        )
        assert revealed.value == "plaintext-value-123"
        assert revealed.key == "REVEAL_KEY"


@pytest.mark.asyncio
async def test_tenant_admin_cannot_reveal_secret(client, admin_headers):
    """admin do tenant não pode revelar valor plano -> 403."""
    response = await client.get(
        f"/api/v1/super-admin/tenants/{WR_TENANT_ID}/secrets/{uuid.uuid4()}/reveal",
        headers=admin_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_secret_value_encrypted_at_rest():
    """O valor cifrado no banco não contém o plaintext."""
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        created = await create_secret(
            TenantSecretCreate(key="AT_REST", value="sensitive-plaintext-xyz"),
            db,
            {"user_id": str(uuid.uuid4()), "role": "admin"},
        )
        secret_id = created.id

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        secret = await db.get(TenantSecret, secret_id)
        assert "sensitive-plaintext-xyz" not in secret.encrypted_value
        assert decrypt(secret.encrypted_value) == "sensitive-plaintext-xyz"
