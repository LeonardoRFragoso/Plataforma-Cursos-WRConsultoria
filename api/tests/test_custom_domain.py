import uuid
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.api.routes.super_admin import (
    super_activate_custom_domain,
    super_confirm_custom_domain,
)
from app.api.routes.tenants import (
    get_custom_domain,
    remove_custom_domain,
    set_custom_domain,
    verify_custom_domain,
)
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.core.tenant import TenantResolver
from app.models.tenant import CustomDomainStatus, Tenant, TenantStatus
from app.schemas.tenant import CustomDomainIn


@asynccontextmanager
async def tenant_context():
    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        yield
    finally:
        current_tenant_id.reset(token)


@pytest.mark.asyncio
async def test_get_custom_domain():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        result = await get_custom_domain(db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.id == WR_TENANT_ID


@pytest.mark.asyncio
async def test_set_custom_domain_pending_with_token():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = CustomDomainIn(custom_domain="Acme-Cursos.COM")
        result = await set_custom_domain(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.custom_domain == "acme-cursos.com"
        # Nunca ACTIVE apenas por digitar; fica PENDING com token
        assert result.custom_domain_status == CustomDomainStatus.PENDING
        assert result.domain_verification_token is not None
        assert len(result.domain_verification_token) > 0
        assert result.dns_instructions is not None
        assert result.dns_instructions["record_type"] == "TXT"
        assert "acme-cursos.com" in result.dns_instructions["host"]


@pytest.mark.asyncio
async def test_set_and_remove_custom_domain():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = CustomDomainIn(custom_domain="Acme-Cursos.COM")
        result = await set_custom_domain(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.custom_domain == "acme-cursos.com"

        removed = await remove_custom_domain(db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert removed.custom_domain is None
        assert removed.custom_domain_status == CustomDomainStatus.NONE


@pytest.mark.asyncio
async def test_set_invalid_custom_domain():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = CustomDomainIn(custom_domain="-invalid-.com")
        with pytest.raises(HTTPException) as exc:
            await set_custom_domain(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_set_custom_domain_already_in_use():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        other = Tenant(
            name="Other",
            slug="other",
            custom_domain="acme-cursos.com",
            custom_domain_status=CustomDomainStatus.ACTIVE,
            status=TenantStatus.ACTIVE,
            contact_name="Other",
            contact_email="other@test.com",
        )
        db.add(other)
        await db.commit()

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = CustomDomainIn(custom_domain="acme-cursos.com")
        with pytest.raises(HTTPException) as exc:
            await set_custom_domain(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_verify_custom_domain_mock_provider_returns_error(monkeypatch):
    """Provider mock retorna False -> status ERROR."""
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = CustomDomainIn(custom_domain="verify-error.com")
        await set_custom_domain(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        result = await verify_custom_domain(db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.custom_domain_status == CustomDomainStatus.ERROR
        assert result.domain_verification_error is not None


@pytest.mark.asyncio
async def test_verify_custom_domain_success(monkeypatch):
    """Provider retorna True -> status VERIFIED."""

    class OkProvider:
        async def verify_txt(self, domain, token):
            return True

    monkeypatch.setattr(
        "app.api.routes.tenants.get_domain_verification_provider",
        lambda: OkProvider(),
    )

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = CustomDomainIn(custom_domain="verify-ok.com")
        await set_custom_domain(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        result = await verify_custom_domain(db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.custom_domain_status == CustomDomainStatus.VERIFIED
        assert result.domain_verified_at is not None


@pytest.mark.asyncio
async def test_super_admin_confirm_and_activate_custom_domain():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = CustomDomainIn(custom_domain="manual-confirm.com")
        await set_custom_domain(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        confirmed = await super_confirm_custom_domain(
            WR_TENANT_ID, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert confirmed.custom_domain_status == CustomDomainStatus.VERIFIED

        activated = await super_activate_custom_domain(
            WR_TENANT_ID, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert activated.custom_domain_status == CustomDomainStatus.ACTIVE


@pytest.mark.asyncio
async def test_activate_requires_verified():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = CustomDomainIn(custom_domain="not-verified.com")
        await set_custom_domain(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        with pytest.raises(HTTPException) as exc:
            await super_activate_custom_domain(
                WR_TENANT_ID, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
            )
        assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_tenant_resolver_only_uses_verified_or_active_domain():
    """TenantResolver não resolve domínios não verificados."""
    from app.models.tenant import Tenant as T

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        pending = T(
            name="Pending",
            slug="pending-tenant",
            custom_domain="pending.example.com",
            custom_domain_status=CustomDomainStatus.PENDING,
            status=TenantStatus.ACTIVE,
            contact_name="P",
            contact_email="p@test.com",
        )
        db.add(pending)
        active = T(
            name="Active",
            slug="active",
            custom_domain="active.example.com",
            custom_domain_status=CustomDomainStatus.ACTIVE,
            status=TenantStatus.ACTIVE,
            contact_name="A",
            contact_email="a@test.com",
        )
        db.add(active)
        await db.commit()
        active_id = active.id

    resolver = TenantResolver()

    class FakeRequest:
        def __init__(self, host):
            self.headers = {"host": host}

    # Domínio ACTIVE resolve para o tenant correto
    async with AsyncSessionLocal() as db:
        active_tenant = await resolver.resolve(FakeRequest("active.example.com"), db)
        assert active_tenant.id == active_id

    # Domínio PENDING não resolve para o tenant pendente (status não verificado)
    async with AsyncSessionLocal() as db:
        with pytest.raises(HTTPException) as exc:
            await resolver.resolve(FakeRequest("pending.example.com"), db)
        assert exc.value.status_code == 404
