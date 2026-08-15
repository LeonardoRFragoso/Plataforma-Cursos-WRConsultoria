import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from app.api.routes.tenant_subscriptions import (
    _end_date_for_cycle,
    activate_subscription,
    cancel_subscription,
    create_subscription,
    get_subscription,
    list_subscriptions,
    renew_subscription,
)
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.models.plan import BillingCycle, Plan
from app.models.tenant_subscription import SubscriptionStatus, TenantSubscription
from app.schemas.tenant_subscription import TenantSubscriptionCreate


@asynccontextmanager
async def tenant_context():
    token = current_tenant_id.set(WR_TENANT_ID)
    try:
        yield
    finally:
        current_tenant_id.reset(token)


async def _seed_plan(db):
    plan = Plan(
        tenant_id=WR_TENANT_ID,
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


@pytest.mark.asyncio
async def test_list_subscriptions():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_plan(db)
        sub = TenantSubscription(
            tenant_id=WR_TENANT_ID,
            plan_id=plan.id,
            status=SubscriptionStatus.PENDENTE,
        )
        db.add(sub)
        await db.commit()

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        result = await list_subscriptions(db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert len(result) == 1
        assert result[0].plan_id == plan.id


@pytest.mark.asyncio
async def test_create_subscription():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_plan(db)

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = TenantSubscriptionCreate(plan_id=plan.id)
        result = await create_subscription(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.plan_id == plan.id
        assert result.status == SubscriptionStatus.PENDENTE


@pytest.mark.asyncio
async def test_create_subscription_plan_not_found():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = TenantSubscriptionCreate(plan_id=uuid.uuid4())
        with pytest.raises(HTTPException) as exc:
            await create_subscription(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_activate_and_renew_subscription():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_plan(db)
        sub = TenantSubscription(
            tenant_id=WR_TENANT_ID,
            plan_id=plan.id,
            status=SubscriptionStatus.PENDENTE,
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        activated = await activate_subscription(sub.id, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert activated.status == SubscriptionStatus.ATIVO
        assert activated.start_date is not None
        assert activated.end_date is not None

        renewed = await renew_subscription(sub.id, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert renewed.status == SubscriptionStatus.ATIVO
        assert renewed.end_date is not None

        found = await get_subscription(sub.id, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert found.status == SubscriptionStatus.ATIVO


def test_end_date_for_cycle():
    start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert _end_date_for_cycle(start, BillingCycle.MONTHLY) == start + timedelta(days=30)
    assert _end_date_for_cycle(start, BillingCycle.YEARLY) == start + timedelta(days=365)
    assert _end_date_for_cycle(start, BillingCycle.ONE_TIME) is None


@pytest.mark.asyncio
async def test_cancel_subscription():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_plan(db)
        sub = TenantSubscription(
            tenant_id=WR_TENANT_ID,
            plan_id=plan.id,
            status=SubscriptionStatus.ATIVO,
        )
        db.add(sub)
        await db.commit()
        await db.refresh(sub)

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        result = await cancel_subscription(sub.id, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.status == SubscriptionStatus.CANCELADO
