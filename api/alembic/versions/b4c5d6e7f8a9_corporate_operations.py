"""corporate operations lifecycle

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_tenant_rls(table: str) -> None:
    policy = f"tenant_isolation_{table}"
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {policy} ON {table} FOR ALL TO public "
        f"USING (current_setting('app.bypass_rls', true) = '1' "
        f"OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
        f"WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
        f"OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def upgrade() -> None:
    op.add_column("companies", sa.Column("billing_email", sa.String(), nullable=True))
    op.add_column("companies", sa.Column("contract_reference", sa.String(), nullable=True))
    op.add_column(
        "companies",
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
    )
    op.add_column("companies", sa.Column("notes", sa.Text(), nullable=True))
    op.create_index("ix_companies_status", "companies", ["status"], unique=False)
    op.alter_column("companies", "status", server_default=None)

    op.create_table(
        "corporate_training_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("cnpj", sa.String(), nullable=True),
        sa.Column("contact_name", sa.String(), nullable=False),
        sa.Column("contact_email", sa.String(), nullable=False),
        sa.Column("contact_phone", sa.String(), nullable=True),
        sa.Column("course_interest", sa.String(), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="NEW"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_corporate_training_requests_tenant_id", "corporate_training_requests", ["tenant_id"])
    op.create_index("ix_corporate_training_requests_status", "corporate_training_requests", ["status"])
    op.create_index("ix_corporate_training_requests_contact_email", "corporate_training_requests", ["contact_email"])
    op.create_index("ix_corporate_training_requests_cnpj", "corporate_training_requests", ["cnpj"])

    op.create_table(
        "corporate_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("students.id"), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("token_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("one_time_tokens.id"), nullable=True),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_corporate_invites_tenant_id", "corporate_invites", ["tenant_id"])
    op.create_index("ix_corporate_invites_company_id", "corporate_invites", ["company_id"])
    op.create_index("ix_corporate_invites_student_id", "corporate_invites", ["student_id"])
    op.create_index("ix_corporate_invites_email", "corporate_invites", ["email"])
    op.create_index("ix_corporate_invites_status", "corporate_invites", ["status"])

    op.create_table(
        "corporate_seat_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("class_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("seats_reserved", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "company_id", "class_id", name="uq_corporate_seat_tenant_company_class"),
    )
    op.create_index("ix_corporate_seat_allocations_tenant_id", "corporate_seat_allocations", ["tenant_id"])
    op.create_index("ix_corporate_seat_allocations_company_id", "corporate_seat_allocations", ["company_id"])
    op.create_index("ix_corporate_seat_allocations_class_id", "corporate_seat_allocations", ["class_id"])

    for table in ("corporate_training_requests", "corporate_invites", "corporate_seat_allocations"):
        _enable_tenant_rls(table)


def downgrade() -> None:
    for table in ("corporate_seat_allocations", "corporate_invites", "corporate_training_requests"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.drop_table(table)
    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_column("companies", "notes")
    op.drop_column("companies", "status")
    op.drop_column("companies", "contract_reference")
    op.drop_column("companies", "billing_email")
