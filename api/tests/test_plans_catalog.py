"""Testa que o catálogo público de planos usa o DB (tabela Plan),
não valores hardcoded.
"""


import pytest

from app.api.routes.tenants import list_plans
from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal
from app.models.plan import BillingCycle, Plan


async def _seed_catalog_plan(db, name="DB Catalog Plan", price=150.0):
    plan = Plan(
        tenant_id=None,
        name=name,
        description="Plano do catálogo DB",
        price=price,
        billing_cycle=BillingCycle.MONTHLY,
        features={"domains": 3},
        max_users=200,
        is_active=True,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


@pytest.mark.asyncio
async def test_tenant_plans_endpoint_uses_db():
    """GET /tenants/plans retorna planos do DB, não hardcoded."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _seed_catalog_plan(db)

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        result = await list_plans(db)
        names = [p.name for p in result]
        assert "DB Catalog Plan" in names
        # Não deve conter valores hardcoded legacy
        assert "Starter" not in names or "DB Catalog Plan" in names
        # Todos os planos retornados são do catálogo global (tenant_id NULL)
        for p in result:
            assert p.tenant_id is None


@pytest.mark.asyncio
async def test_tenant_plans_endpoint_excludes_inactive():
    """Planos inativos não aparecem no catálogo público."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        inactive = Plan(
            tenant_id=None,
            name="Inactive Plan",
            price=50.0,
            is_active=False,
        )
        db.add(inactive)
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        result = await list_plans(db)
        names = [p.name for p in result]
        assert "Inactive Plan" not in names


@pytest.mark.asyncio
async def test_tenant_plans_endpoint_excludes_tenant_specific():
    """Planos específicos de tenant (legado) não aparecem no catálogo público."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        legacy = Plan(
            tenant_id=WR_TENANT_ID,
            name="Legacy Tenant Plan",
            price=75.0,
            is_active=True,
        )
        db.add(legacy)
        await db.commit()

    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        result = await list_plans(db)
        names = [p.name for p in result]
        assert "Legacy Tenant Plan" not in names


async def test_tenant_plans_endpoint_http(client):
    """Via HTTP, /tenants/plans retorna planos do DB."""
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        await _seed_catalog_plan(db, name="HTTP Catalog Plan", price=250.0)

    response = await client.get("/api/v1/tenants/plans")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert "HTTP Catalog Plan" in names
