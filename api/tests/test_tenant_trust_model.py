"""Tests for the tenant context trust model.

Verifies:
- staging enforces trusted Origin for X-Tenant-Slug (same as production)
- production enforces trusted Origin for X-Tenant-Slug
- development/test allow X-Tenant-Slug without trusted Origin
- X-Tenant-Id is ONLY accepted in dev/test, NOT staging or production
- untrusted Origin + slug → 400
- missing Origin + slug → 400 (in staging/production)
- nonexistent slug → 404
- Referer is parsed as origin (not compared as full URL)
"""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.tenant import (
    TenantResolver,
    is_test_environment,
    requires_trusted_tenant_context,
)
from app.models.tenant import Tenant, TenantStatus


async def _set_rls_bypass(db):
    """Set RLS bypass for test sessions so tenant queries work."""
    await db.execute(text(f"SET LOCAL app.current_tenant = '{WR_TENANT_ID}'"))
    await db.execute(text("SET LOCAL app.bypass_rls = '1'"))


async def _seed_alfa():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        slug = f"alfa-{uuid.uuid4().hex[:6]}"
        alfa = Tenant(
            name="Alfa",
            slug=slug,
            status=TenantStatus.ACTIVE,
            contact_name="A",
            contact_email=f"{slug}@a.test",
        )
        db.add(alfa)
        await db.commit()
        await db.refresh(alfa)
        return alfa.id, slug


class _FakeRequest:
    """Minimal stand-in for Starlette Request for unit tests."""

    def __init__(self, headers=None):
        self.headers = headers or {}


@pytest.mark.asyncio
async def test_staging_requires_trusted_origin_for_slug(monkeypatch):
    """staging + X-Tenant-Slug without trusted Origin → 400."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "staging")
    assert requires_trusted_tenant_context() is True

    _alfa_id, slug = await _seed_alfa()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={"host": "api.example.com", "x-tenant-slug": slug}
        )
        with pytest.raises(Exception) as exc_info:
            await resolver.resolve(request, db)
        assert exc_info.value.status_code == 400
        assert "Untrusted origin" in exc_info.value.detail


@pytest.mark.asyncio
async def test_staging_accepts_slug_with_trusted_origin(monkeypatch):
    """staging + X-Tenant-Slug + trusted Origin → resolves tenant."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "staging")
    monkeypatch.setattr(
        "app.core.tenant.settings.TRUSTED_FRONTEND_ORIGINS",
        ["https://alfa.vercel.app"],
    )

    alfa_id, slug = await _seed_alfa()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={
                "host": "api.example.com",
                "x-tenant-slug": slug,
                "origin": "https://alfa.vercel.app",
            }
        )
        tenant = await resolver.resolve(request, db)
        assert tenant.id == alfa_id


@pytest.mark.asyncio
async def test_production_requires_trusted_origin_for_slug(monkeypatch):
    """production + X-Tenant-Slug without trusted Origin → 400."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "production")
    assert requires_trusted_tenant_context() is True

    _alfa_id, slug = await _seed_alfa()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={"host": "api.example.com", "x-tenant-slug": slug}
        )
        with pytest.raises(Exception) as exc_info:
            await resolver.resolve(request, db)
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_production_accepts_slug_with_trusted_origin(monkeypatch):
    """production + X-Tenant-Slug + trusted Origin → resolves tenant."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "production")
    monkeypatch.setattr(
        "app.core.tenant.settings.TRUSTED_FRONTEND_ORIGINS",
        ["https://wr.vercel.app"],
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={
                "host": "api.example.com",
                "x-tenant-slug": "wr",
                "origin": "https://wr.vercel.app",
            }
        )
        tenant = await resolver.resolve(request, db)
        assert tenant.slug == "wr"


@pytest.mark.asyncio
async def test_staging_rejects_x_tenant_id_header(monkeypatch):
    """staging + X-Tenant-Id → ignored (not accepted)."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "staging")
    assert is_test_environment() is False

    alfa_id, _slug = await _seed_alfa()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        # X-Tenant-Id should be ignored in staging; falls through to host
        request = _FakeRequest(
            headers={"host": "localhost", "x-tenant-id": str(alfa_id)}
        )
        # Without slug header or custom domain, resolves by host → "wr" fallback
        tenant = await resolver.resolve(request, db)
        assert tenant.slug == "wr"  # NOT alfa


@pytest.mark.asyncio
async def test_production_rejects_x_tenant_id_header(monkeypatch):
    """production + X-Tenant-Id → ignored."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "production")
    assert is_test_environment() is False

    alfa_id, _slug = await _seed_alfa()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={"host": "localhost", "x-tenant-id": str(alfa_id)}
        )
        tenant = await resolver.resolve(request, db)
        assert tenant.slug == "wr"  # NOT alfa


@pytest.mark.asyncio
async def test_development_accepts_x_tenant_id_header(monkeypatch):
    """development + X-Tenant-Id → accepted."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "development")
    assert is_test_environment() is True

    alfa_id, _slug = await _seed_alfa()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={"host": "api.example.com", "x-tenant-id": str(alfa_id)}
        )
        tenant = await resolver.resolve(request, db)
        assert tenant.id == alfa_id


@pytest.mark.asyncio
async def test_test_environment_accepts_x_tenant_id_header(monkeypatch):
    """test + X-Tenant-Id → accepted."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "test")
    assert is_test_environment() is True

    alfa_id, _slug = await _seed_alfa()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={"host": "api.example.com", "x-tenant-id": str(alfa_id)}
        )
        tenant = await resolver.resolve(request, db)
        assert tenant.id == alfa_id


@pytest.mark.asyncio
async def test_development_accepts_slug_without_trusted_origin(monkeypatch):
    """development + X-Tenant-Slug without Origin → accepted (local)."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "development")
    assert requires_trusted_tenant_context() is False

    alfa_id, slug = await _seed_alfa()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={"host": "api.example.com", "x-tenant-slug": slug}
        )
        tenant = await resolver.resolve(request, db)
        assert tenant.id == alfa_id


@pytest.mark.asyncio
async def test_nonexistent_slug_returns_404(monkeypatch):
    """staging + trusted Origin + nonexistent slug → 404."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "staging")
    monkeypatch.setattr(
        "app.core.tenant.settings.TRUSTED_FRONTEND_ORIGINS",
        ["https://wr.vercel.app"],
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={
                "host": "api.example.com",
                "x-tenant-slug": "nonexistent-xyz",
                "origin": "https://wr.vercel.app",
            }
        )
        with pytest.raises(Exception) as exc_info:
            await resolver.resolve(request, db)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_untrusted_origin_rejected_in_staging(monkeypatch):
    """staging + untrusted Origin + slug → 400."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "staging")
    monkeypatch.setattr(
        "app.core.tenant.settings.TRUSTED_FRONTEND_ORIGINS",
        ["https://wr.vercel.app"],
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={
                "host": "api.example.com",
                "x-tenant-slug": "wr",
                "origin": "https://evil.example.com",
            }
        )
        with pytest.raises(Exception) as exc_info:
            await resolver.resolve(request, db)
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_missing_origin_rejected_in_staging(monkeypatch):
    """staging + missing Origin + slug → 400."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "staging")
    monkeypatch.setattr(
        "app.core.tenant.settings.TRUSTED_FRONTEND_ORIGINS",
        ["https://wr.vercel.app"],
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={"host": "api.example.com", "x-tenant-slug": "wr"}
        )
        with pytest.raises(Exception) as exc_info:
            await resolver.resolve(request, db)
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_referer_parsed_as_origin(monkeypatch):
    """staging + Referer with path → origin extracted and trusted."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "staging")
    monkeypatch.setattr(
        "app.core.tenant.settings.TRUSTED_FRONTEND_ORIGINS",
        ["https://wr.vercel.app"],
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        # Referer has a path; should be parsed to origin
        request = _FakeRequest(
            headers={
                "host": "api.example.com",
                "x-tenant-slug": "wr",
                "referer": "https://wr.vercel.app/dashboard",
            }
        )
        tenant = await resolver.resolve(request, db)
        assert tenant.slug == "wr"


@pytest.mark.asyncio
async def test_referer_untrusted_origin_rejected(monkeypatch):
    """staging + Referer from untrusted origin → 400."""
    monkeypatch.setattr("app.core.tenant.settings.ENVIRONMENT", "staging")
    monkeypatch.setattr(
        "app.core.tenant.settings.TRUSTED_FRONTEND_ORIGINS",
        ["https://wr.vercel.app"],
    )

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _set_rls_bypass(db)
        resolver = TenantResolver()
        request = _FakeRequest(
            headers={
                "host": "api.example.com",
                "x-tenant-slug": "wr",
                "referer": "https://evil.example.com/page",
            }
        )
        with pytest.raises(Exception) as exc_info:
            await resolver.resolve(request, db)
        assert exc_info.value.status_code == 400
