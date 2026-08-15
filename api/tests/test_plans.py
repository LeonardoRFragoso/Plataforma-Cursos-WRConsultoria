import uuid
from contextlib import asynccontextmanager

import pytest

from app.api.routes.plans import list_public_plans
from app.api.routes.super_admin import (
    super_create_plan,
    super_delete_plan,
    super_get_plan,
    super_list_plans,
    super_update_plan,
)
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.plan import BillingCycle, Plan
from app.schemas.plan import PlanCreate, PlanUpdate


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


@pytest.mark.asyncio
async def test_list_public_plans_only_global_active():
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _seed_global_plan(db)
        # Plano inativo não deve aparecer
        inactive = Plan(
            tenant_id=None,
            name="Old",
            price=10.0,
            is_active=False,
        )
        db.add(inactive)
        # Plano específico de tenant (legado) não deve aparecer no catálogo público
        legacy = Plan(
            tenant_id=WR_TENANT_ID,
            name="Legacy",
            price=50.0,
            is_active=True,
        )
        db.add(legacy)
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        result = await list_public_plans(db)
        names = [p.name for p in result]
        assert names == ["Pro"]
        assert all(p.tenant_id is None for p in result)


@pytest.mark.asyncio
async def test_super_create_plan_global():
    async with privileged_session() as db:
        data = PlanCreate(
            name="Starter",
            price=97.0,
            billing_cycle=BillingCycle.YEARLY,
            features=["1 domínio"],
            max_users=50,
        )
        result = await super_create_plan(
            data, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert result.name == "Starter"
        assert result.tenant_id is None  # catálogo global da WR


@pytest.mark.asyncio
async def test_super_get_update_delete_plan():
    async with privileged_session() as db:
        plan = await _seed_global_plan(db)

    async with privileged_session() as db:
        found = await super_get_plan(
            plan.id, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert found.id == plan.id

    async with privileged_session() as db:
        data = PlanUpdate(name="Pro Max", price=397.0)
        updated = await super_update_plan(
            plan.id, data, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert updated.name == "Pro Max"
        assert updated.price == 397.0

    async with privileged_session() as db:
        await super_delete_plan(
            plan.id, db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        found = await db.get(Plan, plan.id)
        assert found.is_active is False


@pytest.mark.asyncio
async def test_super_list_plans():
    async with privileged_session() as db:
        await _seed_global_plan(db)

    async with privileged_session() as db:
        result = await super_list_plans(
            db, {"user_id": str(uuid.uuid4()), "role": "super_admin"}
        )
        assert len(result) >= 1


# ---- Autorização via HTTP client ----

async def test_tenant_admin_cannot_create_plan(client, admin_headers):
    """admin do tenant não pode criar plano -> 403."""
    response = await client.post(
        "/api/v1/super-admin/plans",
        json={"name": "X", "price": 10.0},
        headers=admin_headers,
    )
    assert response.status_code == 403


async def test_super_admin_creates_plan_via_http(client, super_admin_headers):
    """super_admin cria plano -> OK."""
    response = await client.post(
        "/api/v1/super-admin/plans",
        json={
            "name": "Enterprise",
            "price": 997.0,
            "billing_cycle": "YEARLY",
            "features": ["white label"],
            "max_users": 1000,
        },
        headers=super_admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["tenant_id"] is None


async def test_public_plans_endpoint_no_auth(client):
    """Endpoint público de planos não exige autenticação."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _seed_global_plan(db)

    response = await client.get("/api/v1/plans/public")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert "Pro" in names
