"""P1 governance audit trail and privacy request workflow.

Revision ID: b0c1d2e3f4a5
Revises: a0b1c2d3e4f5
Create Date: 2026-08-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{table} ON {table} FOR ALL TO public "
        f"USING (tenant_id = current_setting('app.current_tenant', true)::UUID) "
        f"WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        # No FK on actor_id: audit evidence must survive user deletion.
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("method", sa.String(length=12), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admin_audit_logs_tenant_id", "admin_audit_logs", ["tenant_id"])
    op.create_index("ix_admin_audit_logs_actor_id", "admin_audit_logs", ["actor_id"])
    op.create_index("ix_admin_audit_logs_request_id", "admin_audit_logs", ["request_id"])
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"])
    op.create_index("ix_admin_audit_logs_tenant_created", "admin_audit_logs", ["tenant_id", "created_at"])
    op.create_index("ix_admin_audit_logs_actor_created", "admin_audit_logs", ["actor_id", "created_at"])

    op.create_table(
        "privacy_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        # No FK: resolution evidence remains available after account lifecycle changes.
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_privacy_requests_tenant_id", "privacy_requests", ["tenant_id"])
    op.create_index("ix_privacy_requests_user_id", "privacy_requests", ["user_id"])
    op.create_index("ix_privacy_requests_request_type", "privacy_requests", ["request_type"])
    op.create_index("ix_privacy_requests_status", "privacy_requests", ["status"])
    op.create_index("ix_privacy_requests_tenant_status", "privacy_requests", ["tenant_id", "status"])
    op.create_index("ix_privacy_requests_user_created", "privacy_requests", ["user_id", "created_at"])

    _enable_rls("admin_audit_logs")
    _enable_rls("privacy_requests")


def downgrade() -> None:
    for table in ("privacy_requests", "admin_audit_logs"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("privacy_requests")
    op.drop_table("admin_audit_logs")
