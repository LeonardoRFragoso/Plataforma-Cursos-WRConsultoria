"""add rls bypass for privileged sessions

Revision ID: 697853c1effe
Revises: d288128bbb94
Create Date: 2026-08-15 08:31:05.058911

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '697853c1effe'
down_revision: str | None = 'd288128bbb94'
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


def _policy(table: str) -> str:
    return f"tenant_isolation_{table}"


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {_policy(table)} ON {table}")
        op.execute(
            f"CREATE POLICY {_policy(table)} ON {table} "
            f"FOR ALL TO public "
            f"USING (current_setting('app.bypass_rls', true) = '1' "
            f"OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
            f"WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
            f"OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
        )


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {_policy(table)} ON {table}")
        op.execute(
            f"CREATE POLICY {_policy(table)} ON {table} "
            f"FOR ALL TO public "
            f"USING (tenant_id = current_setting('app.current_tenant', true)::UUID)"
        )
