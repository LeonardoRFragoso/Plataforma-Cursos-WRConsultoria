import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.api.routes.super_admin import (
    _end_date_for_cycle,
    super_activate_subscription,
    super_cancel_subscription,
    super_create_subscription,
    super_get_subscription,
    super_list_subscriptions,
    super_renew_subscription,
    super_suspend_subscription,
)
from app.api.routes.tenant_subscriptions import (
    get_current_subscription,
    get_subscription,
    list_subscriptions,
)
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.plan import BillingCycle, Plan
from app.models.tenant import Tenant, TenantStatus
from app.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from app.schemas.tenant_subscription import TenantSubscriptionCreate


@asynccontextmanager
async def privileged_session():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        yield db


async def _seed_global_plan(db):
    plan = Plan(
        tenant_id=None,
        name="Pro",
        description="Plano pro",
        price=297.0,
        billing_cycle=BillingCycle.MONTHLY,
        features={"domains": 5},
        max_users=500,
        max_courses=50,
        is_active=True,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def _seed_tenant(db, slug="acme"):
    tenant = Tenant(
        name=slug.upper(),
        slug=slug,
        status=TenantStatus.ACTIVE,
        contact_name=slug,
        contact_email=f"{slug}@test.com",
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


def test_end_date_for_cycle():
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert _end_date_for_cycle(start, BillingCycle.MONTHLY) == start + timedelta(days=30)
    assert _end_date_for_cycle(start, BillingCycle.YEARLY) == start + timedelta(days=365)
    assert _end_date_for_cycle(start, BillingCycle.ONE_TIME) is None


# ---- Tenant admin: somente leitura ----

@pytest.mark.asyncio
async def test_tenant_admin_list_own_subscriptions():
    from app.core.context import current_tenant_id

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_global_plan(db)
        sub = TenantSubscription(
            tenant_id=WR_TENANT_ID,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(sub)
        await db.commit()

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            result = await list_subscriptions(
                db, {"user_id": str(uuid.uuid4()), "role": "admin"}
            )
            assert len(result) == 1
            assert result[0].plan_id == plan.id
    finally:
        current_tenant_id.reset(token)


@pytest.mark.asyncio
async def test_tenant_admin_get_current_subscription():
    from app.core.context import current_tenant_id

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_global_plan(db)
        sub = TenantSubscription(
            tenant_id=WR_TENANT_ID,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(sub)
        await db.commit()

    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            result = await get_current_subscription(
                db, {"user_id": str(uuid.uuid4()), "role": "admin"}
            )
            assert result is not None
            assert result.plan_id == plan.id
    finally:
        current_tenant_id.reset(token)


# ---- Super admin: lifecycle ----

@pytest.mark.asyncio
async def test_super_create_subscription():
    async with privileged_session() as db:
        plan = await _seed_global_plan(db)
        tenant = await _seed_tenant(db)

        data = TenantSubscriptionCreate(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status=SubscriptionStatus.TRIAL,
        )
        result = await super_create_subscription(
            data, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert result.plan_id == plan.id
        assert result.tenant_id == tenant.id
        assert result.status == SubscriptionStatus.TRIAL


@pytest.mark.asyncio
async def test_super_create_subscription_tenant_not_found():
    async with privileged_session() as db:
        plan = await _seed_global_plan(db)
        data = TenantSubscriptionCreate(
            tenant_id=uuid.uuid4(),
            plan_id=plan.id,
        )
        with pytest.raises(HTTPException) as exc:
            await super_create_subscription(
                data, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
            )
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_super_activate_renew_cancel_subscription():
    async with privileged_session() as db:
        plan = await _seed_global_plan(db)
        tenant = await _seed_tenant(db)
        sub = TenantSubscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status=SubscriptionStatus.TRIAL,
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)

    async with privileged_session() as db:
        activated = await super_activate_subscription(
            sub.id, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert activated.status == SubscriptionStatus.ACTIVE
        assert activated.start_date is not None
        assert activated.end_date is not None

        renewed = await super_renew_subscription(
            sub.id, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert renewed.status == SubscriptionStatus.ACTIVE
        assert renewed.end_date is not None

        found = await super_get_subscription(
            sub.id, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert found.status == SubscriptionStatus.ACTIVE

        suspended = await super_suspend_subscription(
            sub.id, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert suspended.status == SubscriptionStatus.SUSPENDED

        cancelled = await super_cancel_subscription(
            sub.id, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert cancelled.status == SubscriptionStatus.CANCELLED


@pytest.mark.asyncio
async def test_super_list_subscriptions():
    async with privileged_session() as db:
        plan = await _seed_global_plan(db)
        tenant = await _seed_tenant(db)
        sub = TenantSubscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(sub)
        await db.commit()

    async with privileged_session() as db:
        result = await super_list_subscriptions(
            db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert len(result) >= 1


# ---- Autorização via HTTP client ----

async def test_tenant_admin_cannot_create_subscription(client, admin_headers):
    """admin do tenant não pode criar/atribuir assinatura -> 403."""
    response = await client.post(
        "/api/v1/super-admin/subscriptions",
        json={"tenant_id": str(WR_TENANT_ID), "plan_id": str(uuid.uuid4())},
        headers=admin_headers,
    )
    assert response.status_code == 403


async def test_tenant_admin_cannot_activate_subscription(client, admin_headers):
    """admin do tenant não pode ativar assinatura -> 403."""
    response = await client.post(
        f"/api/v1/super-admin/subscriptions/{uuid.uuid4()}/activate",
        headers=admin_headers,
    )
    assert response.status_code == 403


async def test_tenant_a_cannot_access_subscription_b(client, admin_headers):
    """Tenant A não acessa assinatura de Tenant B (escopo tenant)."""
    from app.core.context import current_tenant_id

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_global_plan(db)
        tenant_b = await _seed_tenant(db, slug="tenantb")
        sub_b = TenantSubscription(
            tenant_id=tenant_b.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
        )
        db.add(sub_b)
        await db.commit()
        await db.refresh(sub_b)
        sub_b_id = sub_b.id

    # Tenant A (WR) tenta acessar assinatura do Tenant B -> 404 (escopo)
    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        async with AsyncSessionLocal() as db:
            db.info["tenant_id"] = WR_TENANT_ID
            with pytest.raises(HTTPException) as exc:
                await get_subscription(
                    sub_b_id, db, {"user_id": str(uuid.uuid4()), "role": "admin"}
                )
            assert exc.value.status_code == 404
    finally:
        current_tenant_id.reset(token)


async def test_super_admin_creates_and_activates_subscription_via_http(
    client, super_admin_headers
):
    """super_admin cria e ativa assinatura -> OK."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_global_plan(db)
        tenant = await _seed_tenant(db, slug="acme-http")
        plan_id = plan.id
        tenant_id = tenant.id

    create = await client.post(
        "/api/v1/super-admin/subscriptions",
        json={
            "tenant_id": str(tenant_id),
            "plan_id": str(plan_id),
            "status": "TRIAL",
        },
        headers=super_admin_headers,
    )
    assert create.status_code == 201
    sub_id = create.json()["id"]
    assert create.json()["status"] == "TRIAL"

    activate = await client.post(
        f"/api/v1/super-admin/subscriptions/{sub_id}/activate",
        headers=super_admin_headers,
    )
    assert activate.status_code == 200
    assert activate.json()["status"] == "ACTIVE"
