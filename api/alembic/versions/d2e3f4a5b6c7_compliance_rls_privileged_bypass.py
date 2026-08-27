"""Align NR compliance RLS with the platform privileged-session contract.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-08-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    "training_professionals",
    "pedagogical_project_versions",
    "course_compliance_profiles",
    "course_training_professionals",
)


def _policy(table: str) -> str:
    return f"tenant_isolation_{table}"


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS {_policy(table)} ON {table}")
        op.execute(
            f"CREATE POLICY {_policy(table)} ON {table} FOR ALL TO public "
            f"USING (current_setting('app.bypass_rls', true) = '1' "
            f"OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
            f"WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
            f"OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP POLICY IF EXISTS {_policy(table)} ON {table}")
        op.execute(
            f"CREATE POLICY {_policy(table)} ON {table} FOR ALL TO public "
            f"USING (tenant_id = current_setting('app.current_tenant', true)::UUID) "
            f"WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::UUID)"
        )
