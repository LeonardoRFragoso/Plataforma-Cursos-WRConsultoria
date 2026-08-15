import uuid
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.api.routes.tenants import (
    get_custom_domain,
    remove_custom_domain,
    set_custom_domain,
)
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant, TenantStatus
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
async def test_set_and_remove_custom_domain():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = CustomDomainIn(custom_domain="Acme-Cursos.COM")
        result = await set_custom_domain(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.custom_domain == "acme-cursos.com"

        removed = await remove_custom_domain(db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert removed.custom_domain is None


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
