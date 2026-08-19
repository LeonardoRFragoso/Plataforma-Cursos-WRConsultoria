"""Tests for subscription enforcement (SUSPENDED/CANCELLED blocks tenant)."""

import uuid

import pytest

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.models.plan import BillingCycle, Plan
from app.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from app.models.user import User, UserRole


async def _create_admin_and_token(email, tenant_id, role=UserRole.ADMIN):
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        user = User(
            email=email,
            full_name=f"Admin {email}",
            cpf=str(uuid.uuid4().int)[:11],
            password_hash=hash_password("pass123"),
            role=role,
            is_active=True,
            tenant_id=tenant_id,
        )
        db.add(user)
        await db.commit()
        return user.id


async def _set_subscription_status(tenant_id, status):
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = tenant_id
        await db.execute(__import__("sqlalchemy").text(
            f"SET LOCAL app.current_tenant = '{tenant_id}'"
        ))
        await db.execute(__import__("sqlalchemy").text("SET LOCAL app.bypass_rls = '1'"))
        # Create a global plan if not exists
        from sqlalchemy import select
        plan = (await db.execute(select(Plan).where(Plan.tenant_id.is_(None)))).scalars().first()
        if not plan:
            plan = Plan(name="Test Plan", price=99.0, billing_cycle=BillingCycle.MONTHLY, is_active=True)
            db.add(plan)
            await db.flush()

        sub = TenantSubscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status=status,
        )
        db.add(sub)
        await db.commit()


@pytest.mark.asyncio
async def test_active_subscription_allows_access(client):
    """ACTIVE subscription → normal operation (200)."""
    admin_id = await _create_admin_and_token("activeadmin@wr.test", WR_TENANT_ID)
    token = create_access_token(
        {"sub": str(admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
    )
    resp = await client.get(
        "/api/v1/enrollments/",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_suspended_subscription_blocks_access(client):
    """SUSPENDED subscription → 503 for business operations."""
    admin_id = await _create_admin_and_token("suspadmin@wr.test", WR_TENANT_ID)
    await _set_subscription_status(WR_TENANT_ID, SubscriptionStatus.SUSPENDED)
    token = create_access_token(
        {"sub": str(admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
    )
    resp = await client.get(
        "/api/v1/enrollments/",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 503
    assert "temporariamente indispon" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancelled_subscription_blocks_access(client):
    """CANCELLED subscription → 503."""
    admin_id = await _create_admin_and_token("canceladmin@wr.test", WR_TENANT_ID)
    await _set_subscription_status(WR_TENANT_ID, SubscriptionStatus.CANCELLED)
    token = create_access_token(
        {"sub": str(admin_id), "role": "admin", "tenant_id": str(WR_TENANT_ID)}
    )
    resp = await client.get(
        "/api/v1/enrollments/",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_suspended_tenant_auth_still_works(client):
    """SUSPENDED tenant can still authenticate (login is exempt)."""
    await _create_admin_and_token("authadmin@wr.test", WR_TENANT_ID)
    await _set_subscription_status(WR_TENANT_ID, SubscriptionStatus.SUSPENDED)
    # Login endpoint should still work (exempt from enforcement)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "authadmin@wr.test", "password": "pass123"},
        headers={"x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_suspended_tenant_super_admin_still_works(client):
    """SUPER_ADMIN paths are exempt from enforcement."""
    admin_id = await _create_admin_and_token(
        "superadmin@wr.test", WR_TENANT_ID, role=UserRole.SUPER_ADMIN
    )
    await _set_subscription_status(WR_TENANT_ID, SubscriptionStatus.SUSPENDED)
    token = create_access_token(
        {"sub": str(admin_id), "role": "super_admin", "tenant_id": str(WR_TENANT_ID)}
    )
    resp = await client.get(
        "/api/v1/super-admin/plans",
        headers={"Authorization": f"Bearer {token}", "x-tenant-slug": "wr"},
    )
    assert resp.status_code == 200
