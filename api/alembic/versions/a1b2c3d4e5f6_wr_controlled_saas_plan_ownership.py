"""wr controlled saas plan ownership

Torna Plan.tenant_id nullable para suportar o catálogo comercial global
da WR (planos com tenant_id IS NULL) e ajusta a política de RLS de plans
para permitir que qualquer tenant leia os planos globais (catálogo
público), mantendo o isolamento para planos específicos de tenant.
Lifecycle administrativo de assinaturas passa a ser controlado pela WR
(SUPER_ADMIN); o status de TenantSubscription é uma coluna String, então
os novos valores (TRIAL, ACTIVE, PAST_DUE, SUSPENDED, CANCELLED) não
exigem alteração de tipo.

Revision ID: a1b2c3d4e5f6
Revises: c54ab278930a
Create Date: 2026-08-15 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = 'c54ab278930a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Planos do catálogo WR são globais (tenant_id NULL).
    op.alter_column(
        'plans', 'tenant_id',
        existing_type=sa.UUID(),
        nullable=True,
    )

    # Ajusta a política de RLS para permitir leitura pública dos planos
    # globais (tenant_id IS NULL) por qualquer tenant, mantendo o bypass
    # para SUPER_ADMIN e o isolamento para planos específicos de tenant.
    op.execute("DROP POLICY IF EXISTS tenant_isolation_plans ON plans")
    op.execute(
        "CREATE POLICY tenant_isolation_plans ON plans "
        "FOR ALL TO public "
        "USING (tenant_id IS NULL "
        "OR current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
        "WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_plans ON plans")
    op.execute(
        "CREATE POLICY tenant_isolation_plans ON plans "
        "FOR ALL TO public "
        "USING (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
        "WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )
    op.alter_column(
        'plans', 'tenant_id',
        existing_type=sa.UUID(),
        nullable=False,
    )
