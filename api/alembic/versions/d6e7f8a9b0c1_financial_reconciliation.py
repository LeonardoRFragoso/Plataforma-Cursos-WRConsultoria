"""financial reconciliation operations

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation_{table} ON {table} FOR ALL TO public "
        f"USING (current_setting('app.bypass_rls', true) = '1' "
        f"OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
        f"WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
        f"OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def upgrade() -> None:
    op.create_table(
        "financial_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="OPEN"),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("priority", sa.String(), nullable=False, server_default="NORMAL"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution_action", sa.String(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("tenant_id", "payment_id", "status", "priority", "assigned_to"):
        op.create_index(f"ix_financial_reviews_{column}", "financial_reviews", [column])
    op.create_index(
        "uq_financial_review_open_payment",
        "financial_reviews",
        ["payment_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('OPEN', 'IN_REVIEW')"),
    )
    op.alter_column("financial_reviews", "status", server_default=None)
    op.alter_column("financial_reviews", "priority", server_default=None)

    op.create_table(
        "financial_review_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("financial_reviews.id"), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ("tenant_id", "review_id", "payment_id", "event_type"):
        op.create_index(f"ix_financial_review_events_{column}", "financial_review_events", [column])

    _enable_rls("financial_reviews")
    _enable_rls("financial_review_events")


def downgrade() -> None:
    for table in ("financial_review_events", "financial_reviews"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("financial_review_events")
    op.drop_table("financial_reviews")
