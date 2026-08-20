"""enable row level security for multi-tenant isolation

Revision ID: 17e4c0870485
Revises: d00868304926
Create Date: 2026-08-15 00:08:23.402543

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '17e4c0870485'
down_revision: str | None = 'd00868304926'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TENANT_TABLES = [
    'attendances',
    'certificates',
    'classes',
    'companies',
    'courses',
    'enrollments',
    'lesson_materials',
    'lesson_progress',
    'lessons',
    'payments',
    'students',
    'users',
]


def upgrade() -> None:
    """Habilita RLS e cria políticas de isolamento por tenant."""
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"FOR ALL TO public "
            f"USING (tenant_id = current_setting('app.current_tenant', true)::UUID)"
        )


def downgrade() -> None:
    """Remove as políticas RLS."""
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
