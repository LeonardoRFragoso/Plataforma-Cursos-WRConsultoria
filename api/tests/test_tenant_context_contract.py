"""Tests for the trusted frontend tenant context contract (X-Tenant-Slug).

Covers:
- trusted origin + slug → correct tenant
- untrusted origin in production → rejected
- missing origin in production + slug header → rejected
- nonexistent slug → 404
- dev mode allows slug header without origin trust
- JWT tenant binding enforced across HTTP (403 on mismatch)
"""

import uuid
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.core.tenant import TenantResolver
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User, UserRole


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}
        self.state = {}


@asynccontextmanager
async def _seed_alfa_tenant():
    """Cria um tenant Alfa de teste e retorna seu id."""
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
        yield alfa.id


# ------------------------------------------------------------------
# TenantResolver — X-Tenant-Slug contract
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slug_header_resolves_tenant_in_dev():
    """Em dev, X-Tenant-Slug resolve o tenant sem exigir Origin confiável."""
    async with _seed_alfa_tenant() as alfa_id:
        resolver = TenantResolver()
        req = FakeRequest({"host": "api.test", "x-tenant-slug": "alfa"})
        async with AsyncSessionLocal() as db:
            tenant = await resolver.resolve(req, db)
            assert tenant.id == alfa_id


@pytest.mark.asyncio
async def test_slug_header_wr_resolves_wr():
    resolver = TenantResolver()
    req = FakeRequest({"host": "api.test", "x-tenant-slug": "wr"})
    async with AsyncSessionLocal() as db:
        tenant = await resolver.resolve(req, db)
        assert tenant.id == WR_TENANT_ID


@pytest.mark.asyncio
async def test_slug_header_nonexistent_slug_returns_404():
    resolver = TenantResolver()
    req = FakeRequest({"host": "api.test", "x-tenant-slug": "nope"})
    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as exc:
            await resolver.resolve(req, db)
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_production_untrusted_origin_rejected(monkeypatch):
    """Em produção, X-Tenant-Slug de origem não confiável é rejeitado (400)."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        settings,
        "TRUSTED_FRONTEND_ORIGINS",
        ["https://wr-demo.vercel.app"],
    )
    resolver = TenantResolver()
    req = FakeRequest(
        {
            "host": "api.railway.app",
            "x-tenant-slug": "alfa",
            "origin": "https://evil.example.com",
        }
    )
    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as exc:
            await resolver.resolve(req, db)
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_production_missing_origin_rejected(monkeypatch):
    """Em produção, X-Tenant-Slug sem Origin é rejeitado."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        settings,
        "TRUSTED_FRONTEND_ORIGINS",
        ["https://wr-demo.vercel.app"],
    )
    resolver = TenantResolver()
    req = FakeRequest({"host": "api.railway.app", "x-tenant-slug": "wr"})
    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as exc:
            await resolver.resolve(req, db)
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_production_trusted_origin_allowed(monkeypatch):
    """Em produção, X-Tenant-Slug de origem confiável resolve o tenant."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        settings,
        "TRUSTED_FRONTEND_ORIGINS",
        ["https://alfa-demo.vercel.app"],
    )
    async with _seed_alfa_tenant() as alfa_id:
        resolver = TenantResolver()
        req = FakeRequest(
            {
                "host": "api.railway.app",
                "x-tenant-slug": "alfa",
                "origin": "https://alfa-demo.vercel.app",
            }
        )
        async with AsyncSessionLocal() as db:
            tenant = await resolver.resolve(req, db)
            assert tenant.id == alfa_id


# ------------------------------------------------------------------
# HTTP-level JWT cross-tenant isolation
# ------------------------------------------------------------------


async def _create_user(email, password, role, tenant_id):
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        user = User(
            email=email,
            full_name=f"User {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password(password),
            role=role,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        return user.id


@pytest.mark.asyncio
async def test_http_wr_admin_token_against_alfa_slug_returns_403(client, monkeypatch):
    """Token WR admin + X-Tenant-Slug=alfa → 403 (JWT tenant mismatch)."""
    async with _seed_alfa_tenant():
        wr_admin_id = await _create_user(
            "wradmin@wr.test", "pass123", UserRole.ADMIN, WR_TENANT_ID
        )
        token = create_access_token(
            {"sub": str(wr_admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
        )
        # Use admin-protected endpoint (enrollments list requires admin auth)
        resp = await client.get(
            "/api/v1/enrollments/",
            headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_http_alfa_admin_token_against_wr_slug_returns_403(client):
    """Token Alfa admin + X-Tenant-Slug=wr → 403."""
    async with _seed_alfa_tenant() as alfa_id:
        alfa_admin_id = await _create_user(
            "alfaadmin@alfa.test", "pass123", UserRole.ADMIN, alfa_id
        )
        token = create_access_token(
            {"sub": str(alfa_admin_id), "role": "admin", "tenant_id": str(alfa_id)}
        )
        resp = await client.get(
            "/api/v1/enrollments/",
            headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_http_wr_student_token_against_alfa_slug_returns_403(client):
    """Token WR student + X-Tenant-Slug=alfa → 403."""
    async with _seed_alfa_tenant():
        wr_student_id = await _create_user(
            "wrstudent@wr.test", "pass123", UserRole.STUDENT, WR_TENANT_ID
        )
        token = create_access_token(
            {
                "sub": str(wr_student_id),
                "role": "student",
                "tenant_id": str(WR_TENANT_ID),
            }
        )
        resp = await client.get(
            "/api/v1/enrollments/me",
            headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "alfa"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_http_wr_admin_token_against_wr_slug_allowed(client):
    """Token WR admin + X-Tenant-Slug=wr → 200 (allowed)."""
    wr_admin_id = await _create_user(
        "wradmin2@wr.test", "pass123", UserRole.ADMIN, WR_TENANT_ID
    )
    token = create_access_token(
        {"sub": str(wr_admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
    )
    resp = await client.get(
        "/api/v1/enrollments/",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_http_refresh_token_does_not_switch_tenant(client):
    """Refresh token não troca de tenant: emite novo token com mesmo tenant_id."""
    async with _seed_alfa_tenant() as alfa_id:
        alfa_admin_id = await _create_user(
            "alfaadmin2@alfa.test", "pass123", UserRole.ADMIN, alfa_id
        )
        from app.core.security import create_refresh_token

        refresh = create_refresh_token(
            {"sub": str(alfa_admin_id), "role": "admin", "tenant_id": str(alfa_id)}
        )
        # Refresh contra contexto WR deve falhar: o novo access token teria
        # tenant_id=alfa, mas o contexto resolvido é WR → 403 no primeiro uso.
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
            headers={"x-tenant-slug": "wr"},
        )
        # O endpoint /refresh usa get_db (depende do contexto) mas não
        # get_current_user, então o refresh em si pode devolver 200 com um
        # token de tenant alfa. O teste importante é que o token resultante
        # não pode ser usado contra WR:
        if resp.status_code == 200:
            new_token = resp.json()["access_token"]
            resp2 = await client.get(
                "/api/v1/enrollments/",
                headers={
                    "Authorization": f"Bearer {new_token}",
                    "x-tenant-slug": "wr",
                },
            )
            assert resp2.status_code == 403
        else:
            # Se o refresh rejeitar por contexto, também é aceitável.
            assert resp.status_code in (403, 404)
