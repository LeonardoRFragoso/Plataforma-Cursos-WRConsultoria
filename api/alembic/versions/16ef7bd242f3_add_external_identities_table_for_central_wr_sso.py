"""add external_identities table for central wr sso

Revision ID: 16ef7bd242f3
Revises: 3f273adccf42
Create Date: 2026-09-01 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "16ef7bd242f3"
down_revision: str | None = "3f273adccf42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("external_subject", sa.String(length=255), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_subject",
            name="uq_external_identity_provider_subject",
        ),
    )
    op.create_index(
        op.f("ix_external_identities_provider"),
        "external_identities",
        ["provider"],
    )
    op.create_index(
        op.f("ix_external_identities_external_subject"),
        "external_identities",
        ["external_subject"],
    )
    op.create_index(
        op.f("ix_external_identities_user_id"),
        "external_identities",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_external_identities_tenant_id"),
        "external_identities",
        ["tenant_id"],
    )

    # Row Level Security — same pattern as other tenant-scoped tables.
    op.execute("ALTER TABLE external_identities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_identities FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_external_identities "
        "ON external_identities FOR ALL TO public "
        "USING (tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_external_identities ON external_identities")
    op.execute("ALTER TABLE external_identities NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_identities DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_external_identities_tenant_id"), table_name="external_identities")
    op.drop_index(op.f("ix_external_identities_user_id"), table_name="external_identities")
    op.drop_index(op.f("ix_external_identities_external_subject"), table_name="external_identities")
    op.drop_index(op.f("ix_external_identities_provider"), table_name="external_identities")
    op.drop_table("external_identities")
