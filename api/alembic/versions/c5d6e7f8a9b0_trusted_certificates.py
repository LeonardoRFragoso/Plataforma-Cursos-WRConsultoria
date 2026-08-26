"""trusted certificate lifecycle

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("certificate_validity_days", sa.Integer(), nullable=True))

    op.drop_constraint("certificates_enrollment_id_key", "certificates", type_="unique")
    op.add_column("certificates", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("certificates", sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"))
    op.add_column("certificates", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(
        "certificates",
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certificates.id"), nullable=True),
    )
    op.add_column("certificates", sa.Column("revoked_at", sa.DateTime(), nullable=True))
    op.add_column(
        "certificates",
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("certificates", sa.Column("revocation_reason", sa.Text(), nullable=True))
    op.add_column("certificates", sa.Column("content_hash", sa.String(), nullable=True))
    op.create_index("ix_certificates_enrollment_id", "certificates", ["enrollment_id"])
    op.create_index("ix_certificates_expires_at", "certificates", ["expires_at"])
    op.create_index("ix_certificates_status", "certificates", ["status"])
    op.create_index("ix_certificates_content_hash", "certificates", ["content_hash"])
    op.create_index(
        "uq_certificate_active_per_enrollment",
        "certificates",
        ["enrollment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.alter_column("certificates", "status", server_default=None)
    op.alter_column("certificates", "version", server_default=None)

    op.create_table(
        "certificate_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("certificate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("certificates.id"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_certificate_events_tenant_id", "certificate_events", ["tenant_id"])
    op.create_index("ix_certificate_events_certificate_id", "certificate_events", ["certificate_id"])
    op.create_index("ix_certificate_events_event_type", "certificate_events", ["event_type"])
    op.execute("ALTER TABLE certificate_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE certificate_events FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_certificate_events ON certificate_events FOR ALL TO public "
        "USING (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID) "
        "WITH CHECK (current_setting('app.bypass_rls', true) = '1' "
        "OR tenant_id = current_setting('app.current_tenant', true)::UUID)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_certificate_events ON certificate_events")
    op.execute("ALTER TABLE certificate_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE certificate_events DISABLE ROW LEVEL SECURITY")
    op.drop_table("certificate_events")
    op.drop_index("uq_certificate_active_per_enrollment", table_name="certificates")
    op.drop_index("ix_certificates_content_hash", table_name="certificates")
    op.drop_index("ix_certificates_status", table_name="certificates")
    op.drop_index("ix_certificates_expires_at", table_name="certificates")
    op.drop_index("ix_certificates_enrollment_id", table_name="certificates")
    op.drop_column("certificates", "content_hash")
    op.drop_column("certificates", "revocation_reason")
    op.drop_column("certificates", "revoked_by")
    op.drop_column("certificates", "revoked_at")
    op.drop_column("certificates", "supersedes_id")
    op.drop_column("certificates", "version")
    op.drop_column("certificates", "status")
    op.drop_column("certificates", "expires_at")
    op.create_unique_constraint("certificates_enrollment_id_key", "certificates", ["enrollment_id"])
    op.drop_column("courses", "certificate_validity_days")
