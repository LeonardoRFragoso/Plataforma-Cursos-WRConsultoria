"""Testa FORCE ROW LEVEL SECURITY nas tabelas SaaS novas.

Usa engine.connect() + conn.begin() com SET LOCAL ROLE para alternar
para um role não-superuser, pois superusers sempre bypassam RLS (mesmo
com FORCE). AsyncSessionLocal().begin() cria um savepoint, não uma
transação real, então SET LOCAL não se aplica corretamente.

Verifica que:
- tenant_secrets: um tenant não consegue ler secrets de outro tenant
- tenant_subscriptions: um tenant não consegue ler subscriptions de outro
- plans: planos globais (tenant_id NULL) são legíveis por qualquer tenant,
  mas planos específicos de tenant só são visíveis pelo próprio tenant
- bypass_rls = '1' permite acesso total (SUPER_ADMIN)
"""

import uuid

import pytest
from sqlalchemy import text

from app.core.constants import WR_TENANT_ID
from app.core.database import AsyncSessionLocal, engine
from app.models.plan import BillingCycle, Plan
from app.models.tenant import Tenant, TenantStatus
from app.models.tenant_secret import TenantSecret
from app.models.tenant_subscription import (
    SubscriptionStatus,
    TenantSubscription,
)
from app.services.secret_crypto import encrypt

RLS_TEST_ROLE = "rls_test_role"


async def _ensure_test_role():
    """Cria um role não-superuser para testar RLS e aplica políticas RLS.

    O conftest.py usa Base.metadata.create_all que não aplica as
    migrações Alembic (RLS). Esta função cria o role, aplica RLS e
    políticas nas tabelas SaaS, e garante os grants necessários.
    """
    async with engine.connect() as conn:
        # Cria role não-superuser
        await conn.execute(
            text(
                f"DO $$ BEGIN IF NOT EXISTS "
                f"(SELECT 1 FROM pg_roles WHERE rolname = '{RLS_TEST_ROLE}') "
                f"THEN CREATE ROLE {RLS_TEST_ROLE} NOSUPERUSER NOCREATEDB NOCREATEROLE; "
                f"END IF; END $$;"
            )
        )

        # Aplica RLS + FORCE + políticas nas tabelas SaaS
        # (create_all não aplica migrações Alembic)
        rls_config = [
            (
                "tenant_secrets",
                (
                    "current_setting('app.bypass_rls', true) = '1' "
                    "OR tenant_id = current_setting('app.current_tenant', true)::UUID"
                ),
            ),
            (
                "tenant_subscriptions",
                (
                    "current_setting('app.bypass_rls', true) = '1' "
                    "OR tenant_id = current_setting('app.current_tenant', true)::UUID"
                ),
            ),
            (
                "plans",
                (
                    "tenant_id IS NULL "
                    "OR current_setting('app.bypass_rls', true) = '1' "
                    "OR tenant_id = current_setting('app.current_tenant', true)::UUID"
                ),
            ),
        ]
        for table, policy_expr in rls_config:
            await conn.execute(
                text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            )
            await conn.execute(
                text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
            )
            await conn.execute(
                text(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
            )
            await conn.execute(
                text(
                    f"CREATE POLICY tenant_isolation_{table} ON {table} "
                    f"FOR ALL TO public "
                    f"USING ({policy_expr}) "
                    f"WITH CHECK ({policy_expr})"
                )
            )

        # Grants
        for table in [
            "tenant_secrets",
            "tenant_subscriptions",
            "plans",
            "tenants",
        ]:
            await conn.execute(
                text(f"GRANT SELECT, INSERT, UPDATE ON {table} TO {RLS_TEST_ROLE}")
            )
        await conn.execute(
            text(f"GRANT USAGE ON SCHEMA public TO {RLS_TEST_ROLE}")
        )
        await conn.commit()


async def _create_tenant(db, slug, name):
    """Cria um tenant de teste e retorna seu ID."""
    tenant = Tenant(
        name=name,
        slug=slug,
        contact_name=f"Admin {name}",
        contact_email=f"admin@{slug}.test",
        status=TenantStatus.ACTIVE,
    )
    db.add(tenant)
    await db.flush()
    return tenant.id


async def _rls_query_as_tenant(tenant_id, table_name):
    """Executa SELECT na tabela como um role não-superuser com
    app.current_tenant definido. Retorna lista de (id, tenant_id) tuples.
    """
    async with engine.connect() as conn, conn.begin():
        await conn.execute(text(f"SET LOCAL ROLE {RLS_TEST_ROLE}"))
        await conn.execute(
            text(f"SET LOCAL app.current_tenant = '{tenant_id}'")
        )
        result = await conn.execute(
            text(f"SELECT id, tenant_id FROM {table_name}")
        )
        return result.fetchall()


@pytest.mark.asyncio
async def test_tenant_secrets_rls_isolation():
    """Tenant A não pode ler secrets do Tenant B."""
    await _ensure_test_role()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant_a = await _create_tenant(db, f"rls-a-{uuid.uuid4().hex[:6]}", "Tenant A")
        tenant_b = await _create_tenant(db, f"rls-b-{uuid.uuid4().hex[:6]}", "Tenant B")

        db.add_all([
            TenantSecret(tenant_id=tenant_a, key="key_a", encrypted_value=encrypt("a")),
            TenantSecret(tenant_id=tenant_b, key="key_b", encrypted_value=encrypt("b")),
        ])
        await db.commit()

    # Tenant A só deve ver seus secrets
    rows_a = await _rls_query_as_tenant(tenant_a, "tenant_secrets")
    for row in rows_a:
        assert row[1] == tenant_a, f"RLS leak: tenant A sees secret from {row[1]}"

    # Tenant B só deve ver seus secrets
    rows_b = await _rls_query_as_tenant(tenant_b, "tenant_secrets")
    for row in rows_b:
        assert row[1] == tenant_b, f"RLS leak: tenant B sees secret from {row[1]}"


@pytest.mark.asyncio
async def test_tenant_subscriptions_rls_isolation():
    """Tenant A não pode ler subscriptions do Tenant B."""
    await _ensure_test_role()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant_a = await _create_tenant(db, f"rls-sub-a-{uuid.uuid4().hex[:6]}", "Tenant Sub A")
        tenant_b = await _create_tenant(db, f"rls-sub-b-{uuid.uuid4().hex[:6]}", "Tenant Sub B")

        plan = Plan(
            tenant_id=None,
            name="RLS Sub Test Plan",
            price=100.0,
            billing_cycle=BillingCycle.MONTHLY,
            is_active=True,
        )
        db.add(plan)
        await db.flush()

        db.add_all([
            TenantSubscription(tenant_id=tenant_a, plan_id=plan.id, status=SubscriptionStatus.ACTIVE),
            TenantSubscription(tenant_id=tenant_b, plan_id=plan.id, status=SubscriptionStatus.ACTIVE),
        ])
        await db.commit()

    # Tenant A só deve ver suas subscriptions
    rows_a = await _rls_query_as_tenant(tenant_a, "tenant_subscriptions")
    for row in rows_a:
        assert row[1] == tenant_a, f"RLS leak: tenant A sees sub from {row[1]}"

    # Tenant B só deve ver suas subscriptions
    rows_b = await _rls_query_as_tenant(tenant_b, "tenant_subscriptions")
    for row in rows_b:
        assert row[1] == tenant_b, f"RLS leak: tenant B sees sub from {row[1]}"


@pytest.mark.asyncio
async def test_plans_rls_global_catalog_visible_to_all_tenants():
    """Planos globais (tenant_id NULL) são legíveis por qualquer tenant."""
    await _ensure_test_role()
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant_a = await _create_tenant(db, f"rls-plan-a-{uuid.uuid4().hex[:6]}", "Tenant Plan A")

        global_plan = Plan(
            tenant_id=None,
            name="Global RLS Plan",
            price=50.0,
            billing_cycle=BillingCycle.MONTHLY,
            is_active=True,
        )
        tenant_plan = Plan(
            tenant_id=tenant_a,
            name="Tenant A Specific Plan",
            price=75.0,
            billing_cycle=BillingCycle.MONTHLY,
            is_active=True,
        )
        db.add_all([global_plan, tenant_plan])
        await db.commit()

    # Tenant A deve ver ambos (global + específico)
    rows_a = await _rls_query_as_tenant(tenant_a, "plans")
    plan_ids = {row[0] for row in rows_a}
    assert global_plan.id in plan_ids, "Tenant A should see global plan"
    assert tenant_plan.id in plan_ids, "Tenant A should see its own plan"

    # Outro tenant (não-A) só deve ver planos globais
    other_tenant = uuid.uuid4()
    rows_other = await _rls_query_as_tenant(other_tenant, "plans")
    plan_ids_other = {row[0] for row in rows_other}
    assert global_plan.id in plan_ids_other, "Other tenant should see global plan"
    assert tenant_plan.id not in plan_ids_other, (
        "Other tenant should NOT see tenant A's specific plan"
    )


@pytest.mark.asyncio
async def test_bypass_rls_allows_super_admin_access():
    """Sessão com bypass_rls='1' (SUPER_ADMIN) acessa todos os tenants.

    Usa o role postgres (superuser) que naturalmente bypassa RLS.
    """
    async with AsyncSessionLocal() as db:
        db.info["tenant_id"] = WR_TENANT_ID
        tenant_a = await _create_tenant(db, f"rls-bypass-a-{uuid.uuid4().hex[:6]}", "Bypass A")
        tenant_b = await _create_tenant(db, f"rls-bypass-b-{uuid.uuid4().hex[:6]}", "Bypass B")

        db.add_all([
            TenantSecret(tenant_id=tenant_a, key="bypass_a", encrypted_value=encrypt("a")),
            TenantSecret(tenant_id=tenant_b, key="bypass_b", encrypted_value=encrypt("b")),
        ])
        await db.commit()

    # Sessão superuser — deve ver ambos
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tenant_id FROM tenant_secrets WHERE key LIKE 'bypass_%'")
        )
        tenant_ids = {row[0] for row in result.fetchall()}
        assert tenant_a in tenant_ids
        assert tenant_b in tenant_ids
