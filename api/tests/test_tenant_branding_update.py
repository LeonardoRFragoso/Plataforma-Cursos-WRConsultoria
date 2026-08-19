"""Tests for PUT /api/v1/tenants/branding (tenant admin self-service)."""

import uuid

import pytest

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole


async def _create_tenant_admin(email, password, tenant_id):
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        user = User(
            email=email,
            full_name=f"Admin {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        return user.id


async def _seed_alfa():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        alfa = Tenant(
            name="Alfa Academy",
            slug="alfa",
            status=TenantStatus.ACTIVE,
            contact_name="Alfa Admin",
            contact_email="admin@alfa.test",
            primary_color="#E86A17",
        )
        db.add(alfa)
        await db.commit()
        await db.refresh(alfa)
        return alfa.id


@pytest.mark.asyncio
async def test_admin_updates_own_branding(client):
    """Admin atualiza branding do próprio tenant."""
    admin_id = await _create_tenant_admin("brandadmin@wr.test", "pass123", WR_TENANT_ID)
    token = create_access_token(
        {"sub": str(admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
    )
    resp = await client.put(
        "/api/v1/tenants/branding",
        json={
            "name": "WR Cursos Atualizado",
            "primary_color": "#FF0000",
            "accent_color": "#00FF00",
        },
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "WR Cursos Atualizado"
    assert body["primary_color"] == "#FF0000"
    assert body["accent_color"] == "#00FF00"
    # Campos não enviados permanecem inalterados
    assert body["logo_url"] is None


@pytest.mark.asyncio
async def test_student_cannot_update_branding(client):
    """Student não pode atualizar branding → 403."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        user = User(
            email="studentbrand@wr.test",
            full_name="Student",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=UserRole.STUDENT,
            is_active=True,
            tenant_id=WR_TENANT_ID,
        )
        db.add(user)
        await db.commit()
        uid = user.id

    token = create_access_token(
        {"sub": str(uid), "role": "student", "tenant_id": str(WR_TENANT_ID)}
    )
    resp = await client.put(
        "/api/v1/tenants/branding",
        json={"name": "Hacked"},
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_alfa_admin_cannot_update_wr(client):
    """Admin Alfa não pode atualizar branding de WR."""
    alfa_id = await _seed_alfa()
    alfa_admin_id = await _create_tenant_admin(
        "alfaadmin@alfa.test", "pass123", alfa_id
    )
    token = create_access_token(
        {"sub": str(alfa_admin_id), "role": "admin", "tenant_id": str(alfa_id)}
    )
    # Tenta atualizar WR com token Alfa → 403 (JWT mismatch)
    resp = await client.put(
        "/api/v1/tenants/branding",
        json={"name": "Hacked WR"},
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invalid_hex_color_rejected(client):
    """Cor inválida é rejeitada (422)."""
    admin_id = await _create_tenant_admin("coloradmin@wr.test", "pass123", WR_TENANT_ID)
    token = create_access_token(
        {"sub": str(admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
    )
    resp = await client.put(
        "/api/v1/tenants/branding",
        json={"primary_color": "red"},
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_url_rejected(client):
    """URL não-http é rejeitada."""
    admin_id = await _create_tenant_admin("urladmin@wr.test", "pass123", WR_TENANT_ID)
    token = create_access_token(
        {"sub": str(admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
    )
    resp = await client.put(
        "/api/v1/tenants/branding",
        json={"logo_url": "javascript:alert(1)"},
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_no_auth_returns_401(client):
    """Sem token → 401."""
    resp = await client.put(
        "/api/v1/tenants/branding",
        json={"name": "No Auth"},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code in (401, 403)
