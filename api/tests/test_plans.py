import uuid
from contextlib import asynccontextmanager

import pytest

from app.api.routes.plans import create_plan, delete_plan, get_plan, list_plans, update_plan
from app.core.constants import WR_TENANT_ID
from app.core.context import current_tenant_id
from app.core.database import AsyncSessionLocal
from app.models.plan import BillingCycle, Plan
from app.schemas.plan import PlanCreate, PlanUpdate


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
async def test_list_plans():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _seed_plan(db)

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        result = await list_plans(db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert len(result) == 1
        assert result[0].name == "Pro"


@pytest.mark.asyncio
async def test_create_plan():
    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = PlanCreate(
            name="Starter",
            price=97.0,
            billing_cycle=BillingCycle.YEARLY,
            features=["1 domínio"],
            max_users=50,
        )
        result = await create_plan(data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.name == "Starter"
        assert result.tenant_id == WR_TENANT_ID


@pytest.mark.asyncio
async def test_get_plan():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_plan(db)

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        result = await get_plan(plan.id, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.id == plan.id


@pytest.mark.asyncio
async def test_update_plan():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_plan(db)

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        data = PlanUpdate(name="Pro Max", price=397.0)
        result = await update_plan(plan.id, data, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        assert result.name == "Pro Max"
        assert result.price == 397.0


@pytest.mark.asyncio
async def test_delete_plan():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        plan = await _seed_plan(db)

    async with AsyncSessionLocal() as db, tenant_context():
        db.info["tenant_id"] = WR_TENANT_ID
        await delete_plan(plan.id, db, {"user_id": str(uuid.uuid4()), "role": "admin"})
        found = await db.get(Plan, plan.id)
        assert found.is_active is False
