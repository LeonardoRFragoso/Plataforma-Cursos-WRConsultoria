"""force RLS on SaaS subscription and secret tables

Aplica FORCE ROW LEVEL SECURITY nas tabelas tenant-aware novas que
estavam apenas com ENABLE ROW LEVEL SECURITY:

- tenant_secrets
- tenant_subscriptions
- plans (mantém a política especial que permite leitura de planos
  globais tenant_id IS NULL)

O FORCE garante que o owner da tabela (postgres) também esteja sujeito
às políticas, a menos que a sessão tenha bypass_rls = '1' (SUPER_ADMIN).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-15 16:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


TABLES = ["tenant_secrets", "tenant_subscriptions", "plans"]


def upgrade() -> None:
    """Aplica FORCE ROW LEVEL SECURITY nas tabelas SaaS."""
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Remove FORCE ROW LEVEL SECURITY (mantém ENABLE)."""
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
