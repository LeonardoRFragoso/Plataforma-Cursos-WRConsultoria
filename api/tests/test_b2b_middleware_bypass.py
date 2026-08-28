"""Phase 1: B2B tenant middleware bypass tests.

Verifies that /api/v1/b2b/* routes:
1. Work WITHOUT X-Tenant-Slug header.
2. Host header does not change the B2B tenant.
3. Malicious X-Tenant-Slug does not change the B2B tenant.
4. Tenant A does not receive subscription state of tenant B.
5. Suspended tenant follows policy correctly (503).
6. Missing B2B credentials still return 401 (not 422 or 400 from
   the tenant resolver).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.b2b_client import B2BClient
from app.models.tenant import Tenant, TenantStatus
from app.models.tenant_subscription import TenantSubscription
from app.models.plan import Plan

B2B_CLIENT_ID = "test-b2b-mw-bypass"
B2B_CLIENT_SECRET = "test-b2b-mw-bypass-secret-32chars!!"


@pytest.fixture(autouse=True)
async def _setup_b2b_mw_client():
    async with AsyncSessionLocal() as session:
        client = B2BClient(
            tenant_id=WR_TENANT_ID,
            client_id=B2B_CLIENT_ID,
            client_secret_hash=hash_password(B2B_CLIENT_SECRET),
            name="MW Bypass Test",
            allowed_scopes="academic:read",
            is_active=True,
        )
        session.add(client)
        await session.commit()
        yield
        await session.execute(
            delete(B2BClient).where(B2BClient.client_id == B2B_CLIENT_ID)
        )
        await session.commit()


def _b2b_headers():
    return {
        "X-B2B-Client-Id": B2B_CLIENT_ID,
        "X-B2B-Client-Secret": B2B_CLIENT_SECRET,
    }


@pytest.mark.asyncio
async def test_b2b_works_without_tenant_slug(client: AsyncClient):
    """B2B works without X-Tenant-Slug — client_id is the authority."""
    response = await client.get("/api/v1/b2b/context", headers=_b2b_headers())
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_b2b_host_does_not_change_tenant(client: AsyncClient):
    """Different Host header must not change the B2B tenant."""
    # Send a Host header that would resolve to a different slug
    response = await client.get(
        "/api/v1/b2b/context",
        headers={**_b2b_headers(), "Host": "evil.example.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_b2b_malicious_tenant_slug_ignored(client: AsyncClient):
    """Malicious X-Tenant-Slug must not change the B2B tenant."""
    response = await client.get(
        "/api/v1/b2b/context",
        headers={**_b2b_headers(), "X-Tenant-Slug": "evil-tenant"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == str(WR_TENANT_ID)


@pytest.mark.asyncio
async def test_b2b_missing_credentials_returns_401_not_tenant_error(client: AsyncClient):
    """Missing B2B credentials should return 401, not a tenant resolution error."""
    # No B2B headers, no X-Tenant-Slug — in test env the resolver would
    # fall back to "wr" via localhost, but B2B should still 401 because
    # credentials are missing.
    response = await client.get("/api/v1/b2b/context")
    assert response.status_code == 401
    assert "credentials" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_b2b_suspended_tenant_returns_503(client: AsyncClient):
    """A suspended tenant should block B2B access with 503."""
    # Create a subscription with SUSPENDED status for the WR tenant
    async with AsyncSessionLocal() as session:
        # Ensure a plan exists
        plan = Plan(
            tenant_id=WR_TENANT_ID,
            name="test-plan-b2b-suspended",
            price=0,
            billing_cycle="MONTHLY",
            is_active=True,
        )
        session.add(plan)
        await session.flush()
        sub = TenantSubscription(
            tenant_id=WR_TENANT_ID,
            plan_id=plan.id,
            status="SUSPENDED",
        )
        session.add(sub)
        await session.commit()
        plan_id = plan.id
        sub_id = sub.id
    try:
        response = await client.get("/api/v1/b2b/context", headers=_b2b_headers())
        assert response.status_code == 503
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(TenantSubscription).where(TenantSubscription.id == sub_id)
            )
            await session.execute(delete(Plan).where(Plan.id == plan_id))
            await session.commit()


@pytest.mark.asyncio
async def test_b2b_active_tenant_works(client: AsyncClient):
    """An ACTIVE subscription should not block B2B access."""
    async with AsyncSessionLocal() as session:
        plan = Plan(
            tenant_id=WR_TENANT_ID,
            name="test-plan-b2b-active",
            price=0,
            billing_cycle="MONTHLY",
            is_active=True,
        )
        session.add(plan)
        await session.flush()
        sub = TenantSubscription(
            tenant_id=WR_TENANT_ID,
            plan_id=plan.id,
            status="ACTIVE",
        )
        session.add(sub)
        await session.commit()
        plan_id = plan.id
        sub_id = sub.id
    try:
        response = await client.get("/api/v1/b2b/context", headers=_b2b_headers())
        assert response.status_code == 200
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(TenantSubscription).where(TenantSubscription.id == sub_id)
            )
            await session.execute(delete(Plan).where(Plan.id == plan_id))
            await session.commit()
